"""AE Si FX E3.1: reversible opacity preview and non-destructive VFX audit.

Only operates on five E3-generated, exact source-identified Si ink materials.
Seven DefaultHGMaterial vfxpart meshes are *classified*, never silently hidden,
reparented, re-shaded, or relabeled as hair; native FX equations are unknown.
No changes to other characters/profiles, source geometry or rigging.
"""
from __future__ import annotations

import math
import re

import bpy

from . import ae_fx_ink_sources as e3
from . import ae_material_sources as dictionary

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
REVISION = 'AE_SI_FX_E31_OPACITY_PREVIEW_1'
CALIBRATION_KEY = 'SaberShader_AE_FX_E31_Calibration'
PREVIOUS_KEY = 'SaberShader_AE_FX_E31_PreviousOpacity'
PREVIEW_FACTOR = 0.25
E3_OPACITY_NODE = e3.NODE_PREFIX + 'User opacity / preview'
A_B_ACTIVE_KEY = 'SaberShader_AE_E3_OpacityTest_Original'
VFX_PATTERN = re.compile(r'^S_actor_jsspsi_vfxpart_0[1-7]_lod0(?:\.\d{3})?$', re.I)


def legacy_e3_opacity(record):
    """Actual E3 opacity calculation, not native Unity's opacity equation."""
    tint = record.get('selected_colors', {}).get('_BlendTint', {})
    return max(0.12, e3._c(tint.get('a', 0.65), 0.65))


def _si_mesh(obj):
    return (getattr(obj, 'type', None) == 'MESH'
            and 'jsspsi' in str(getattr(obj, 'name', '')).casefold())


def _node_for(mat):
    if not getattr(mat, 'use_nodes', False):
        return None
    tree = getattr(mat, 'node_tree', None)
    return tree.nodes.get(E3_OPACITY_NODE) if tree else None


def _previous_state(mat, key):
    return (key in mat, mat.get(key))


def _restore_property(mat, key, state):
    if state[0]:
        mat[key] = state[1]
    elif key in mat:
        del mat[key]


def calibrate_e3_opacity(objects, *, catalog=None, factor=PREVIEW_FACTOR):
    """Transactional, idempotent E3 -> E3.1 preview on exact five Si materials.

    Does not overwrite manual node edits, active A/B tests, shared-outside-scope
    materials, linked materials, or previously calibrated values. The E3 marker
    and original-material link remain unchanged for the existing Restore tool.
    """
    if not isinstance(factor, (int, float)) or not math.isfinite(factor) or not 0.0 < factor <= 1.0:
        raise ValueError('E3.1 preview factor must be finite in (0,1]')
    catalog = catalog or dictionary._source_catalog()
    unique = {}
    slot_use = {}
    for obj in objects or ():
        if not _si_mesh(obj):
            continue
        mesh = getattr(obj, 'data', None)
        for mat in getattr(mesh, 'materials', ()) or ():
            if mat is None or mat.get(e3.MARKER, '') != e3.REVISION:
                continue
            identity = (mat.as_pointer() if hasattr(mat, 'as_pointer') else id(mat))
            unique[identity] = mat
            slot_use[identity] = slot_use.get(identity, 0) + 1
    planned, skipped, already = [], [], 0
    for key, mat in unique.items():
        source_name = str(mat.get('AEF_V11_SourceMaterial', '') or '')
        record = catalog.get('materials', {}).get(source_name)
        if source_name not in e3.TARGET_SOURCES or record is None or record.get('category') != 'fx_maintex':
            skipped.append((mat.name, 'UNVERIFIED_FX_SOURCE'))
            continue
        if mat.get(CALIBRATION_KEY, '') == REVISION:
            already += 1
            continue
        if getattr(mat, 'library', None) is not None or getattr(mat, 'override_library', None) is not None:
            skipped.append((mat.name, 'LINKED_MATERIAL'))
            continue
        # Blender material.users also counts a fake user. Do not modify a
        # shared datablock used by another actor outside this Build selection.
        usage = getattr(mat, 'users', None)
        expected_max = slot_use[key] + int(bool(getattr(mat, 'use_fake_user', False)))
        if isinstance(usage, int) and usage > expected_max:
            skipped.append((mat.name, 'MATERIAL_SHARED_OUTSIDE_SELECTION'))
            continue
        if A_B_ACTIVE_KEY in mat:
            skipped.append((mat.name, 'ACTIVE_A_B_TEST_RESTORE_FIRST'))
            continue
        node = _node_for(mat)
        if node is None:
            skipped.append((mat.name, 'E3_OPACITY_NODE_MISSING'))
            continue
        try:
            socket = node.inputs[1]
            current = float(socket.default_value)
        except (TypeError, ValueError, KeyError, IndexError, AttributeError):
            skipped.append((mat.name, 'E3_OPACITY_SOCKET_UNAVAILABLE'))
            continue
        authored_e3 = legacy_e3_opacity(record)
        if not math.isfinite(current) or not math.isclose(current, authored_e3, rel_tol=1e-4, abs_tol=1e-5):
            skipped.append((mat.name, 'CUSTOM_OPACITY_PRESERVED'))
            continue
        target = authored_e3 * factor
        planned.append((mat, socket, current, target))
    done = []
    try:
        for mat, socket, previous, target in planned:
            state = (_previous_state(mat, PREVIOUS_KEY), _previous_state(mat, CALIBRATION_KEY))
            # Snapshot prior state before changing either socket or metadata.
            done.append((mat, socket, previous, state))
            mat[PREVIOUS_KEY] = previous
            socket.default_value = target
            mat[CALIBRATION_KEY] = REVISION
    except Exception as exc:
        failures = []
        for mat, socket, previous, state in reversed(done):
            try:
                socket.default_value = previous
                _restore_property(mat, PREVIOUS_KEY, state[0])
                _restore_property(mat, CALIBRATION_KEY, state[1])
            except Exception as rollback_error:
                failures.append(str(rollback_error))
        return {'status': 'ROLLBACK_INCOMPLETE' if failures else 'ERROR_ROLLED_BACK',
                'calibrated': 0, 'already': already, 'skipped': skipped,
                'error': str(exc), 'rollback_errors': failures}
    return {'status': 'CALIBRATED' if planned else ('ALREADY_CALIBRATED' if already else 'NO_ELIGIBLE_E3'),
            'calibrated': len(planned), 'already': already,
            'skipped': skipped, 'factor': factor, 'total_e3': len(unique)}


def restore_e3_opacity(objects):
    """Undo only the E3.1 opacity preview, not the original E3 FX material."""
    targets = {}
    selected_slots = {}
    if any(_si_mesh(obj) and any(m and m.get('SaberShader_AE_FX_E331') == 'AE_SI_FX_E331_LOOK_MATCH_1'
                                  for m in getattr(getattr(obj, 'data', None), 'materials', ()) or ())
           for obj in objects or ()):
        return {'status': 'BLOCKED', 'errors': ['RESTORE_E3_3_1_FIRST'], 'restored': 0}
    for obj in objects or ():
        if not _si_mesh(obj):
            continue
        for mat in getattr(getattr(obj, 'data', None), 'materials', ()) or ():
            if mat is None or mat.get(e3.MARKER, '') != e3.REVISION or mat.get(CALIBRATION_KEY, '') != REVISION:
                continue
            identity = mat.as_pointer() if hasattr(mat,'as_pointer') else id(mat)
            targets[identity] = mat
            selected_slots[identity] = selected_slots.get(identity, 0) + 1
    planned, errors = [], []
    for identity, mat in targets.items():
        usage = getattr(mat, 'users', None)
        expected_max = selected_slots[identity] + int(bool(getattr(mat, 'use_fake_user', False)))
        if isinstance(usage, int) and usage > expected_max:
            errors.append(mat.name + ': SHARED_OUTSIDE_SI_SELECTION')
            continue
        node = _node_for(mat)
        if (getattr(mat, 'library', None) is not None or
                getattr(mat, 'override_library', None) is not None or node is None or PREVIOUS_KEY not in mat):
            errors.append(mat.name + ': MISSING_BACKUP_OR_UNEDITABLE')
            continue
        try:
            old = float(mat[PREVIOUS_KEY])
            current = float(node.inputs[1].default_value)
            if not all(map(math.isfinite, (old, current))):
                raise ValueError('non-finite opacity')
            planned.append((mat, node.inputs[1], current, old))
        except (TypeError, ValueError, KeyError, IndexError, AttributeError):
            errors.append(mat.name + ': INVALID_PREVIEW')
    if errors:
        return {'status': 'BLOCKED', 'errors': errors, 'restored': 0}
    done=[]
    try:
        for mat, socket, current, baseline in planned:
            # metadata is removed only after all socket writes succeed
            socket.default_value = baseline
            done.append((mat, socket, current))
    except Exception as exc:
        for mat, socket, current in reversed(done):
            try: socket.default_value = current
            except Exception: pass
        return {'status':'ERROR_ROLLED_BACK','error':str(exc),'restored':0}
    for mat, socket, current, baseline in planned:
        del mat[CALIBRATION_KEY]
        del mat[PREVIOUS_KEY]
    return {'status':'RESTORED','restored':len(planned)}


def classify_vfxparts(objects, *, catalog=None):
    """Read-only exact provenance classifier. Does NOT change render state."""
    catalog = catalog or dictionary._source_catalog()
    matches = []
    for obj in objects or ():
        if getattr(obj, 'type', None) != 'MESH' or not VFX_PATTERN.fullmatch(str(getattr(obj, 'name',''))):
            continue
        mats = list(getattr(getattr(obj, 'data', None), 'materials', ()) or ())
        names = []
        source_ids = []
        for mat in mats:
            if mat is None:
                continue
            names.append(str(mat.name))
            raw = mat.get('AEF_V11_SourceMaterial', '')
            source_id = str(raw or '')
            source_ids.append(source_id)
        verified = (len(mats) == 1 and mats[0] is not None
                    and source_ids == ['DefaultHGMaterial']
                    and 'DefaultHGMaterial' in catalog.get('materials', {}))
        row = {'object':obj.name, 'materials':names, 'source_ids':source_ids,
               'status':'VFX_PLACEHOLDER_DEFAULT_HG' if verified else 'VFX_SOURCE_UNVERIFIED',
               'visual_equivalence':'UNVERIFIED', 'changed':False}
        if verified:
            mode = str(getattr(mats[0], 'surface_render_method', 'UNKNOWN'))
            row['surface_render_method'] = mode
            row['hair_shader_assigned'] = any(name.startswith('SaberShader - Hair') for name in names)
            row['opaque_status'] = 'UNKNOWN_WITHOUT_SHADER_RENDER_CHECK'
        matches.append(row)
    verified_count = sum(r['status']=='VFX_PLACEHOLDER_DEFAULT_HG' for r in matches)
    return {'status':'CLASSIFIED_READ_ONLY' if matches else 'NO_VFXPART',
            'recognized':verified_count, 'found':len(matches),
            'unverified':len(matches)-verified_count,
            'render_equivalence':'NOT_VERIFIED', 'rows':matches}


class AEF_OT_ae_si_fx_e31_restore_opacity(bpy.types.Operator):
    bl_idname = 'sabershader.ae_si_fx_e31_restore_opacity'
    bl_label = 'Restore Si FX Opacity (Advanced)'
    bl_description = 'Undo only the FX opacity preview; retain original materials and source assets'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            result = restore_e3_opacity(dictionary._target_meshes(context))
        except Exception as exc:
            self.report({'ERROR'},'Si FX opacity restore failed: '+str(exc)[:160])
            return {'CANCELLED'}
        if result['status'] != 'RESTORED' or not result['restored']:
            self.report({'WARNING'},'No FX opacity preview restored: '+str(result.get('errors',result['status']))[:135])
            return {'CANCELLED'}
        self.report({'INFO'}, 'Restored earlier E3 opacity for %d FX materials' % result['restored'])
        return {'FINISHED'}
