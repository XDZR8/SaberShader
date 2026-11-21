"""E3.4.2 AE Universal FX Foundation: actor-isolated, read-only source audit.

Compatibility: keeps Si E3.4.1 A/B and all legacy Build stages untouched.
It does NOT create a material, relink images, change scene data, or enable
an FX profile for another character. E3.4.3 will add optional previews.
"""
from __future__ import annotations

import json
import tempfile
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import bpy

from .ae_ui_visibility import ae_developer_tools_visible

from . import ae_fx_universal_core as core

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'
REVISION = core.REVISION


def _readonly(item):
    return bool(getattr(item, 'library', None) or getattr(item, 'override_library', None))


def _actor_from_objects(objects):
    ids = {core.actor_id(getattr(obj, 'name', '')) for obj in (objects or ())
           if getattr(obj, 'type', None) == 'MESH'}
    ids.discard('')
    if len(ids) != 1:
        raise ValueError('Require exactly one canonical AE actor (found %s)' % ', '.join(sorted(ids)))
    return next(iter(ids))


def _manual_scope(context):
    """Only active/selected actor, never infer from a whole mixed scene."""
    active = getattr(context, 'active_object', None)
    selected = list(getattr(context, 'selected_objects', ()) or ())
    if active is None:
        raise ValueError('Select a single AE actor mesh or its armature')
    actor = core.actor_id(getattr(active, 'name', ''))
    if not actor:
        descendants = []
        for obj in context.scene.objects:
            parent = getattr(obj, 'parent', None)
            for _ in range(32):
                if parent is None:
                    break
                if parent is active:
                    descendants.append(obj)
                    break
                parent = getattr(parent, 'parent', None)
        actor = _actor_from_objects(descendants)
    other = {core.actor_id(getattr(o, 'name', '')) for o in selected
             if o is not active and getattr(o, 'type', None) == 'MESH'}
    other.discard('')
    if other and other != {actor}:
        raise ValueError('Multiple AE characters selected: isolate one actor')
    objects = [obj for obj in context.scene.objects
               if getattr(obj, 'type', None) == 'MESH' and core.actor_id(obj.name) == actor]
    if not objects:
        raise ValueError('No canonical AE actor meshes in current scene')
    return actor, objects


def _source_folder(context):
    settings = getattr(context.scene, 'aef_sabershader_v8', None)
    folder = str(getattr(settings, 'universal_texture_folder', '') or '')
    if not folder:
        raise ValueError('AE source folder has not been configured')
    return bpy.path.abspath(folder)


def _ae_authorized(context, actor):
    from . import engine
    state = engine._xdzr8_ae_state(context, for_actor=actor)
    if not state.get('authorized', False):
        raise ValueError('AE source is not verified for actor %s: %s' % (actor, state.get('reason', '')))
    # An imported model is insufficient. Must have an exact actor ID recorded
    # from the completed Build; never trust a generic shared material alone.
    built = str(context.scene.get('SaberShader_AEStateV1_ActorId', '') or '').casefold()
    if built != actor:
        raise ValueError('AE Build actor identity missing or mismatched (expected %s)' % actor)


def inspect_actor(context, objects, *, actor=None, require_verified=True):
    if actor is None:
        actor = _actor_from_objects(objects)
    if not actor or any(core.actor_id(o.name) not in ('', actor) for o in objects
                        if getattr(o, 'type', None) == 'MESH'):
        raise ValueError('Actor scope is ambiguous')
    if require_verified:
        _ae_authorized(context, actor)
    folder = _source_folder(context)
    rows, skipped = [], []
    for obj in sorted(objects, key=lambda o: o.name):
        if getattr(obj, 'type', None) != 'MESH' or core.actor_id(obj.name) != actor:
            continue
        mats = getattr(getattr(obj, 'data', None), 'materials', None)
        if mats is None:
            skipped.append({'object': obj.name, 'reason': 'NO_MATERIAL_COLLECTION'})
            continue
        for index, mat in enumerate(mats):
            if mat is None:
                skipped.append({'object': obj.name, 'slot': index, 'reason': 'EMPTY_MATERIAL_SLOT'})
                continue
            exact = mat.get('AEF_V11_SourceMaterial', '')
            source_id, proof = core.source_name(mat.name, exact)
            kind = core.candidate_kind(obj.name, source_id)
            if not kind:
                continue
            owner = core.source_owner(source_id)
            if owner and owner != actor:
                skipped.append({'object': obj.name, 'slot': index, 'reason': 'SOURCE_ACTOR_MISMATCH',
                                'material': mat.name, 'source_material': source_id, 'source_owner': owner})
                continue
            entry = core.source_inventory(source_id, folder, object_name=obj.name)
            # FX on linked meshes/mats can be inventoried but never edited.
            entry.update({'object': obj.name, 'slot': index, 'material': mat.name,
                          'source_proof': proof,
                          'mesh_read_only': _readonly(obj) or _readonly(obj.data),
                          'shared_mesh': getattr(obj.data, 'users', 1) > 1,
                          'material_read_only': _readonly(mat)})
            rows.append(entry)
    counter = Counter(row['family'] for row in rows)
    return {
        'schema': core.SCHEMA,
        'revision': REVISION,
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'read_only': True,
        'actor_id': actor,
        'scope': 'verified single AE actor / exact mesh names and source identity',
        'mesh_count': sum(getattr(o, 'type', None) == 'MESH' and core.actor_id(o.name) == actor for o in objects),
        'fx_material_slot_count': len(rows),
        'family_counts': dict(sorted(counter.items())),
        'rows': rows,
        'skipped': skipped,
        'warnings': [
            'A detected FX family is a candidate, not a reproduced Unity shader equation.',
            'A texture present on disk is not proof it is linked to Material Output.',
            'E3.4.2 inventory never changes, loads, relinks or replaces materials.',
            'Si E3.3.x FX stages are legacy; cross-character FX auto-build is NOT enabled.',
        ],
    }


def export_report(report):
    path = (Path(tempfile.gettempdir()) /
            ('SaberShader_AE_UniversalFX_E342_' +
             datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8] + '.json'))
    with path.open('x', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    return str(path)


def inspect_after_build(context, objects, *, write_report=True):
    """Read-only after successful verified AE Build; never block successful Build."""
    actor = _actor_from_objects(objects)
    result = inspect_actor(context, objects, actor=actor, require_verified=True)
    path = export_report(result) if write_report else ''
    return {'status': 'AUDITED', 'actor': actor, 'slots': len(result['rows']),
            'family_counts': result['family_counts'], 'path': path, 'report': result}


class AEF_OT_ae_universal_fx_e342_audit(bpy.types.Operator):
    bl_idname = 'sabershader.ae_universal_fx_e342_audit'
    bl_label = 'Audit AE Universal FX (Read Only)'
    bl_description = 'Inspect source-authored FX for one verified Endfield actor; export diagnostic JSON without edits'
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            actor, objects = _manual_scope(context)
            result = inspect_actor(context, objects, actor=actor)
            path = export_report(result)
            print('SABERSHADER AE UNIVERSAL FX E3.4.2 READ ONLY:', path)
            self.report({'INFO'}, 'AE FX %s: %s candidate slots, JSON: %s' % (
                actor, len(result['rows']), path[:170]))
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, 'AE Universal FX audit refused: %s' % str(exc)[:170])
            return {'CANCELLED'}


class AEF_PT_ae_universal_fx_e342(bpy.types.Panel):
    bl_label = 'Universal FX Source Inspection'
    bl_idname = 'AEF_PT_ae_universal_fx_e342'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_endfield'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return ae_developer_tools_visible(context)

    def draw(self, context):
        layout = self.layout
        layout.label(text='Source-driven FX inventory for any AE actor', icon='SHADING_TEXTURE')
        layout.label(text='Current stage: diagnosis only, no FX material edits')
        layout.label(text='Select one actor; requires verified AE Build')
        layout.operator('sabershader.ae_universal_fx_e342_audit', text='Audit Universal FX (Read Only)', icon='TEXT')
        layout.label(text='Saved JSON path appears in Blender console')
        layout.label(text='Si A/B comparison is managed separately')
