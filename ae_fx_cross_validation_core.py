"""E3.4.5 pure, deterministic cross-character FX QA comparisons.

No Blender import, network access or shader modification. A comparison never
converts missing evidence into a PASS. A2 appearance is NOT visually judged here.
"""
from __future__ import annotations

import hashlib
import json

SNAP_SCHEMA = 'SaberShader_AE_FX_E345_Snapshot_V1'
RESULT_SCHEMA = 'SaberShader_AE_FX_E345_Comparison_V1'
EVIDENCE_SCHEMA = 'SaberShader_AE_FX_E345_ActorEvidence_V1'
CROSS_SCHEMA = 'SaberShader_AE_FX_E345_CrossCharacter_V1'
REVISION = 'AE_FX_CROSS_CHARACTER_VALIDATION_E345_1'
MODES = ('PREVIEW_A2', 'RESTORED', 'REPEAT_BUILD')
SI_ACTOR = 'jsspsi'


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode('utf-8')).hexdigest()


def _valid_snapshot(data):
    return (isinstance(data, dict) and data.get('schema') == SNAP_SCHEMA and
            isinstance(data.get('actor'), str) and bool(data.get('actor')) and
            isinstance(data.get('objects'), dict) and isinstance(data.get('materials'), dict) and
            isinstance(data.get('images'), dict) and isinstance(data.get('session'), dict) and
            isinstance(data.get('audit'), dict))


def compare(baseline, current, mode):
    """Compare in-memory snapshots, strictly isolating only approved A2 slots.

    No baseline/current value is silently normalized or substituted. In PREVIEW,
    exactly the declared, provenance-checked A2 mesh slots may differ. In
    RESTORED/REPEAT_BUILD every captured property must match its baseline.
    """
    if mode not in MODES:
        raise ValueError('Unsupported E345 comparison mode')
    if not _valid_snapshot(baseline) or not _valid_snapshot(current):
        raise ValueError('Missing or unsupported E345 snapshot')
    findings = []

    def fail(code, detail):
        if len(findings) < 100:
            findings.append({'code': code, 'detail': str(detail)[:240]})

    actor = baseline['actor']
    if current['actor'] != actor:
        fail('ACTOR_CHANGED', '%s -> %s' % (actor, current['actor']))
    for key in ('source_root', 'scene_render', 'images'):
        if baseline.get(key) != current.get(key):
            fail(key.upper() + '_CHANGED', 'E345 protected scene/source settings changed: ' + key)

    b_objs, c_objs = baseline['objects'], current['objects']
    if set(b_objs) != set(c_objs):
        fail('OBJECT_SET_CHANGED', 'added=%s removed=%s' % (
            sorted(set(c_objs) - set(b_objs))[:7], sorted(set(b_objs) - set(c_objs))[:7]))
    b_mats, c_mats = baseline['materials'], current['materials']

    preview_targets = {}
    if mode == 'PREVIEW_A2':
        session = current['session']
        kind = session.get('kind', '')
        expected = 'E344_SI' if actor == SI_ACTOR else 'E343_UNIVERSAL'
        if kind != expected:
            fail('PREVIEW_WRONG_KIND', 'actor=%s, actual=%s, expected=%s' % (actor, kind, expected))
        if baseline['session'].get('kind'):
            fail('BASELINE_PREVIEW_ACTIVE', 'Capture baseline with A visible and no E343/E344 session')
        targets = session.get('targets', [])
        if not isinstance(targets, list) or not targets:
            fail('NO_VERIFIED_A2_TARGETS', 'No active, validated A2 session targets')
            targets = []
        for t in targets:
            if not isinstance(t, dict):
                fail('BAD_TARGET', 'Non-dictionary preview target')
                continue
            obj, slot, original, staged = (t.get('object'), t.get('slot'),
                                           t.get('original'), t.get('staged'))
            if not isinstance(slot, int) or slot < 0 or not isinstance(obj, str):
                fail('BAD_TARGET', str(t))
                continue
            key = (obj, slot)
            if key in preview_targets:
                fail('DUPLICATE_TARGET', str(key))
            preview_targets[key] = t
            previous = b_objs.get(obj, {})
            slots = previous.get('slots', [])
            if (previous.get('actor') != actor or slot >= len(slots) or
                    slots[slot].get('data') != original or original == staged or
                    t.get('current') != 'A2'):
                fail('TARGET_PROVENANCE', '%s[%d] missing/mismatched A source' % (obj, slot))
            if staged not in c_mats:
                fail('MISSING_STAGE_MATERIAL', str(staged))
        additions = set(c_mats) - set(b_mats)
        stages = {t.get('staged') for t in targets if isinstance(t, dict)}
        if additions != stages:
            fail('UNEXPECTED_STAGE_MATERIALS', 'added=%s, approved=%s' % (sorted(additions), sorted(stages)))
        if any(t.get('original') not in b_mats for t in targets if isinstance(t, dict)):
            fail('STAGE_ORIGINAL_NOT_IN_BASELINE', 'Original material name not recorded')
    else:
        if current['session'].get('kind') or current['session'].get('targets'):
            fail('PREVIEW_NOT_RESTORED', 'A/A2 tags still active')
        if set(b_mats) != set(c_mats):
            fail('MATERIAL_SET_CHANGED', 'added=%s removed=%s' % (
                sorted(set(c_mats) - set(b_mats))[:8], sorted(set(b_mats) - set(c_mats))[:8]))
        if baseline.get('audit') != current.get('audit'):
            fail('FX_SOURCE_INVENTORY_CHANGED', 'Candidate family/JSON/texture provenance differs')

    # During PREVIEW the original A may gain a temporary fake user from E343/E344.
    # It is the ONLY allowed change on an original material, and must revert.
    originals = {t.get('original') for t in preview_targets.values()}
    for name, value in b_mats.items():
        actual = c_mats.get(name)
        if mode == 'PREVIEW_A2' and name in originals and isinstance(actual, dict):
            actual = dict(actual)
            actual['fake_user'] = value.get('fake_user')
        if actual != value:
            fail('SOURCE_MATERIAL_MODIFIED', name)

    for obj_name in sorted(set(b_objs) & set(c_objs)):
        b, c = b_objs[obj_name], c_objs[obj_name]
        b_slots, c_slots = b.get('slots', []), c.get('slots', [])
        if len(b_slots) != len(c_slots):
            fail('MESH_SLOT_COUNT_CHANGED', obj_name)
            continue
        b_rest = {k: v for k, v in b.items() if k != 'slots'}
        c_rest = {k: v for k, v in c.items() if k != 'slots'}
        if b_rest != c_rest:
            fail('MESH_IDENTITY_OR_VISIBILITY_CHANGED', obj_name)
        for index, (before, after) in enumerate(zip(b_slots, c_slots)):
            t = preview_targets.get((obj_name, index))
            if t is None:
                if before != after:
                    fail('UNAUTHORIZED_MATERIAL_SLOT_CHANGE', '%s[%d]' % (obj_name, index))
            else:
                if (after.get('data') != t['staged'] or after.get('effective') != t['staged'] or
                        before.get('link') != after.get('link')):
                    fail('A2_NOT_VISIBLE_OR_WRONG_SLOT', '%s[%d]' % (obj_name, index))
    if mode == 'REPEAT_BUILD':
        first = baseline.get('build', {})
        second = current.get('build', {})
        if (not first.get('run_id') or not second.get('run_id') or
                first['run_id'] == second['run_id']):
            fail('REPEAT_BUILD_NOT_PROVEN', 'Distinct native AE Full Setup execution IDs required')
        if (second.get('run_status') != 'FINISHED' or second.get('last_result') != 'FINISHED'
                or second.get('run_event') != 'BUILD' or first.get('run_event') != 'BUILD'):
            fail('REPEAT_BUILD_NOT_FINISHED', 'Latest AE Full Setup and legacy Build must finish')
        if second.get('run_actor') != actor:
            fail('REPEAT_BUILD_ACTOR_MISMATCH', 'AE Full Setup execution belongs to another actor')
    result = {
        'schema': RESULT_SCHEMA, 'revision': REVISION, 'mode': mode, 'actor': actor,
        'status': 'PASS_STATIC' if not findings else 'FAIL',
        'failures': findings, 'object_count': len(b_objs),
        'source_material_count': len(b_mats), 'image_count': len(baseline['images']),
        'preview_target_count': len(preview_targets),
        'preview_kind': current['session'].get('kind', '') if mode == 'PREVIEW_A2' else '',
        'baseline_hash': digest(baseline), 'current_hash': digest(current),
        'fx_baseline': baseline['audit'],
        'disclaimer': 'Static scene/material safety only; Blender images/render visual fidelity NOT measured.',
    }
    return result


def evidence(actor, results, build_snapshot):
    """Compile one actor's three independent phase PASSes; no invented tests."""
    if not _valid_snapshot(build_snapshot) or build_snapshot['actor'] != actor:
        raise ValueError('Invalid current actor Build baseline')
    reasons = []
    for name in MODES:
        result = results.get(name)
        if not isinstance(result, dict) or result.get('schema') != RESULT_SCHEMA or result.get('mode') != name:
            reasons.append('MISSING_' + name)
        elif result.get('actor') != actor or result.get('status') != 'PASS_STATIC':
            reasons.append('FAILED_' + name)
    preview = results.get('PREVIEW_A2') or {}
    expected = 'E344_SI' if actor == SI_ACTOR else 'E343_UNIVERSAL'
    if preview.get('preview_kind') != expected:
        reasons.append('WRONG_PREVIEW_TYPE')
    preview_base_hash = (results.get('PREVIEW_A2') or {}).get('baseline_hash', '')
    restore_base_hash = (results.get('RESTORED') or {}).get('baseline_hash', '')
    if not preview_base_hash or preview_base_hash != restore_base_hash:
        reasons.append('PREVIEW_RESTORE_BASELINE_MISMATCH')
    repeat_base_hash = (results.get('REPEAT_BUILD') or {}).get('baseline_hash', '')
    if repeat_base_hash != digest(build_snapshot):
        reasons.append('REPEAT_BUILD_BASELINE_MISMATCH')
    audit = build_snapshot['audit']
    if actor != SI_ACTOR and audit.get('eligible_preview_slots', 0) < 1:
        reasons.append('NO_VERIFIED_SUPPORTED_SECOND_ACTOR_FX')
    if actor == SI_ACTOR and preview.get('preview_target_count') != 7:
        reasons.append('SI_EXPECTED_SEVEN_IDLE_TARGETS')
    if build_snapshot['session'].get('kind'):
        reasons.append('ACTIVE_AA2_ON_BUILD_BASELINE')
    if actor == SI_ACTOR and audit.get('si_preset_leak', False):
        reasons.append('SI_PRESET_RESIDUAL')
    if actor != SI_ACTOR and audit.get('si_preset_leak', False):
        reasons.append('SI_PRESET_CROSS_ACTOR_LEAK')
    return {
        'schema': EVIDENCE_SCHEMA, 'revision': REVISION, 'actor': actor,
        'status': 'PASS_STATIC' if not reasons else 'INCOMPLETE_OR_FAIL',
        'reasons': reasons, 'phase_results': {k: (results.get(k) or {}).get('status', 'MISSING') for k in MODES},
        'phases': {k: {'baseline_hash': (results.get(k) or {}).get('baseline_hash', ''),
                       'current_hash': (results.get(k) or {}).get('current_hash', ''),
                       'preview_kind': (results.get(k) or {}).get('preview_kind', '')} for k in MODES},
        'fx_audit': audit, 'build_baseline_hash': digest(build_snapshot),
        'disclaimer': 'Native Blender render comparisons and Unity parity must be manually validated.',
    }


def compare_characters(first, second):
    """Cross-character proof requires independent complete Si + another AE actor."""
    problems = []
    for label, data in (('FIRST', first), ('SECOND', second)):
        if not isinstance(data, dict) or data.get('schema') != EVIDENCE_SCHEMA:
            problems.append(label + '_BAD_EVIDENCE')
        elif data.get('status') != 'PASS_STATIC':
            problems.append(label + '_NOT_PASSED')
    a = str(first.get('actor', '')) if isinstance(first, dict) else ''
    b = str(second.get('actor', '')) if isinstance(second, dict) else ''
    if not a or not b or a == b:
        problems.append('NEED_TWO_DISTINCT_ACTORS')
    if SI_ACTOR not in (a, b):
        problems.append('SI_REFERENCE_EVIDENCE_MISSING')
    other = b if a == SI_ACTOR else a
    if other == SI_ACTOR or not other:
        problems.append('SECOND_ACTOR_MISSING')
    if isinstance(first, dict) and isinstance(second, dict):
        for data in (first, second):
            if data.get('actor') != SI_ACTOR and data.get('fx_audit', {}).get('eligible_preview_slots', 0) < 1:
                problems.append('SECOND_ACTOR_NO_SUPPORTED_SOURCE_FX')
    return {
        'schema': CROSS_SCHEMA, 'revision': REVISION, 'actors': [a, b],
        'status': 'PASS_STATIC' if not problems else 'INCOMPLETE_OR_FAIL',
        'problems': sorted(set(problems)),
        'coverage': ['source identity', 'FX family isolation', 'A2 source protection',
                     'restore', 'repeat Build', 'unrelated materials/images'],
        'render_validation': 'PENDING_MANUAL_BLENDER_5_1_1',
        'unity_visual_fidelity': 'NOT_ESTABLISHED',
    }
