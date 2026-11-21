"""AE material source registry and Si texture-audit UI.

Read-only inspection only: no shader changes, material replacements, reparenting,
image relinking or scene settings. Source metadata comes from the supplied
Si - Default materials and texture files. Native Unity FX equations are unknown.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import bpy

from .ae_ui_visibility import ae_developer_tools_visible

SABERSHADER_BUILD_SIGNATURE = '820d6f8746be49c0ac0cb39f3a32d7b4'

from .general_dictionary import ae_material_catalog_for_actor

# The developer audit below still targets Si's existing verified source pack.
# Other actors can be registered through the shared source dictionary without
# inheriting Si-only shader/FX assumptions.
_REPORT_PREFIX = "SaberShader_AE_SourceAudit_Si"


def _source_catalog(actor_code='jsspsi'):
    data = ae_material_catalog_for_actor(actor_code)
    if data is None:
        raise RuntimeError("No verified AE source catalog for actor: " + str(actor_code))
    return data


def normalize_basename(value):
    """Strip only Blender's trailing .001-style duplicate suffix and extension."""
    base = str(value or "").replace("\\", "/").rsplit("/", 1)[-1]
    base = re.sub(r"\.\d{3}$", "", base)
    base = re.sub(r"\.(?:png|jpg|jpeg|tga|dds|exr|bmp|webp)$", "", base, flags=re.I)
    return base.casefold()


def resolve_source(material, catalog):
    """Require exact identity, never match just 'cloth' or 'fx' category."""
    names = []
    try:
        explicit = material.get("AEF_V11_SourceMaterial")
    except Exception:
        explicit = None
    if isinstance(explicit, str) and explicit:
        names.append(explicit)
    names.append(getattr(material, "name", ""))
    raw = catalog.get("materials", {})
    index = {normalize_basename(k): k for k in raw}
    seen = set()
    for candidate in names:
        key = normalize_basename(candidate)
        if key in seen:
            continue
        seen.add(key)
        original = index.get(key)
        if original:
            return original, raw[original], "EXACT_SOURCE_PROPERTY" if candidate == explicit else "EXACT_MATERIAL_NAME"
    return None, None, "NO_EXACT_SOURCE_IDENTITY"


def _linked_images(material):
    """Return only images actually referenced by this material, including groups."""
    result = {}
    visited = set()

    def visit(tree, depth):
        if tree is None or depth > 12:
            return
        try:
            pointer = tree.as_pointer()
        except Exception:
            pointer = id(tree)
        if pointer in visited:
            return
        visited.add(pointer)
        for node in getattr(tree, "nodes", ()):
            image = getattr(node, "image", None)
            if image is not None:
                name = str(getattr(image, "name", ""))
                try:
                    packed = bool(image.packed_file) or len(image.packed_files) > 0
                except (AttributeError, TypeError):
                    packed = False
                path = str(getattr(image, "filepath", "") or "")
                try:
                    exists = bool(path and os.path.isfile(bpy.path.abspath(path, library=image.library)))
                except Exception:
                    exists = False
                # GENERATED/VIEWER images are not disk assets.
                source = str(getattr(image, "source", ""))
                ok = packed or exists or source in {"GENERATED", "VIEWER"}
                key = normalize_basename(name) or normalize_basename(path)
                result.setdefault(key, []).append({
                    "image": name, "filepath": path,
                    "accessible": ok, "packed": packed,
                    "node": str(getattr(node, "name", "")),
                })
            sub = getattr(node, "node_tree", None)
            if sub is not None:
                visit(sub, depth+1)
    if getattr(material, "use_nodes", False):
        visit(getattr(material, "node_tree", None), 0)
    return result


def _target_meshes(context):
    """Scope all findings to the Si actor; never inspect unrelated assets."""
    scene = getattr(context, "scene", None)
    if scene is None:
        return []
    result = []
    for obj in scene.objects:
        if getattr(obj, "type", "") != "MESH":
            continue
        in_name = "jsspsi" in str(obj.name).casefold()
        if not in_name:
            for mat in getattr(obj.data, "materials", ()):
                if mat is None:
                    continue
                try:
                    source = str(mat.get("AEF_V11_SourceMaterial", ""))
                except Exception:
                    source = ""
                if "jsspsi" in (str(mat.name) + source).casefold():
                    in_name = True
                    break
        if in_name:
            result.append(obj)
    return sorted(result, key=lambda item: item.name.casefold())


def _is_generated_sabershader_helper(object_name, material_name):
    """Identify our generated helper *by exact family*, not a source alias."""
    name = str(object_name or '')
    material = str(material_name or '')
    return (name.startswith('SaberShader - Expression Eye Plane - ')
            and material.startswith('SaberShader - Expression Eye Plane - ')) or (
            name.startswith('SaberShader AE Outline | ')
            and material.startswith('SaberShader AE Ink | '))


def inspect_scene(context, catalog=None):
    catalog = catalog or _source_catalog()
    rows=[]
    mesh_list = _target_meshes(context)
    seen_images = {}
    for obj in mesh_list:
        mats = list(getattr(obj.data, "materials", ()) or ())
        if not mats:
            rows.append({"object":obj.name,"slot":None,"status":"NO_MATERIAL_SLOTS"})
            continue
        for slot, mat in enumerate(mats):
            if mat is None:
                rows.append({"object":obj.name,"slot":slot,"status":"EMPTY_MATERIAL_SLOT"})
                continue
            source_name, record, identity = resolve_source(mat, catalog)
            row={"object":obj.name,"slot":slot,"material":mat.name,
                 "source_material":source_name,"identity":identity}
            images=_linked_images(mat)
            row["actual_linked_images"]={k:v for k,v in images.items()}
            for key, entries in images.items():
                seen_images.setdefault(key,[]).extend(entries)
            row["unavailable_image_nodes"]=[v["image"] for entries in images.values() for v in entries if not v["accessible"]]
            if record is None:
                row["status"] = ("GENERATED_SABERSHADER_HELPER"
                                 if _is_generated_sabershader_helper(obj.name, mat.name)
                                 else "UNKNOWN_SOURCE_MATERIAL")
                rows.append(row)
                continue
            category=record["category"]
            expected=record["slots"]
            row["category"]=category
            row["expected_slots"]={key:rec["texture"] for key,rec in expected.items()}
            row["unmatched_source_slots"]={key:rec["texture"] for key,rec in expected.items()
                if normalize_basename(rec["texture"]) not in images}
            row["matched_source_slots"]=[key for key,rec in expected.items()
                if normalize_basename(rec["texture"]) in images]
            if category.startswith("fx_"):
                # FX must not be rendered via the standard opaque _BaseMap branch.
                row["status"]=("FX_PROCEDURAL_UNVERIFIED" if not expected else
                               "FX_SOURCE_TEXTURES_UNBOUND" if row["unmatched_source_slots"] else
                               "FX_IMAGES_FOUND_SHADER_UNVERIFIED")
            elif "_BaseMap" in expected:
                row["status"]=("BASE_MAP_NOT_CONNECTED" if "_BaseMap" in row["unmatched_source_slots"] else
                               "BASE_MAP_CONNECTED")
            else:
                # Exact Si vfxpart + exact DefaultHGMaterial source identity is
                # a VFX placeholder, not missing hair/base color texture.
                # No game-equivalent visibility/material state is inferred.
                is_vfxpart = bool(re.fullmatch(
                    r'S_actor_jsspsi_vfxpart_0[1-7]_lod0(?:\.\d{3})?', obj.name, re.I))
                if is_vfxpart and source_name == 'DefaultHGMaterial':
                    row["category"] = "vfx_placeholder"
                    row["status"] = "VFX_PLACEHOLDER_UNVERIFIED"
                    row["visual_equivalence"] = "NOT_VERIFIED"
                    row["note"] = "Source DefaultHGMaterial: no BaseMap; do not interpret as opaque hair"
                else:
                    row["status"]="NO_BASE_MAP_IN_SOURCE"
            if row["unavailable_image_nodes"]:
                row["status"] += "__INACCESSIBLE_IMAGE_PATH"
            rows.append(row)
    counter = Counter(row["status"] for row in rows)
    return {"schema":"SaberShader_AE_Si_SourceAudit_V1","timestamp_utc":datetime.now(timezone.utc).isoformat(),
            "character":"Si","scope":"only scene meshes with jsspsi object/material/source identity",
            "read_only":True,"mesh_count":len(mesh_list),"material_slot_count":len(rows),
            "status_counts":dict(counter),"warnings":[
               "This audit does not identify render-equivalent Unity FX shader equations.",
               "A source image present in the ZIP is not necessarily connected in Blender.",
               "An image linked in a node tree does not prove it contributes to Material Output.",
               "The concept art's white strokes may be intentional; inspect viewport and material slots.",
            ],"rows":rows}


def _unique_report_path():
    stem=_REPORT_PREFIX+'_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    return Path(tempfile.gettempdir()) / (stem+'.json')


class AEF_OT_ae_si_source_dictionary_audit(bpy.types.Operator):
    bl_idname = "sabershader.ae_si_source_dictionary_audit"
    bl_label = "Audit AE Source Materials (Si)"
    bl_description = "Read-only: compare Si scene materials with exact Unity JSON declarations and image nodes; export JSON to temp"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        try:
            report=inspect_scene(context)
            if not report["mesh_count"]:
                self.report({'WARNING'}, "No Si (jsspsi) meshes found in current scene")
                return {'CANCELLED'}
            path=_unique_report_path()
            with path.open("x", encoding="utf-8") as out:
                json.dump(report,out,ensure_ascii=False,indent=2)
            print('SABERSHADER AE SI SOURCE AUDIT:',str(path))
            counts=report["status_counts"]
            self.report({'INFO'}, "Si: %d meshes, %d slots. JSON: %s"%(
                report["mesh_count"],report["material_slot_count"],str(path)))
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, "AE Si source audit failed: %s: %s"%(type(exc).__name__,str(exc)[:175]))
            return {'CANCELLED'}


class AEF_PT_ae_si_source_dictionary(bpy.types.Panel):
    bl_label = "AE Source Material Dictionary (Si)"
    bl_idname = "AEF_PT_ae_si_source_dictionary"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'SaberShader'
    bl_parent_id = 'AEF_PT_ui121_endfield'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return ae_developer_tools_visible(context)

    def draw(self, context):
        layout=self.layout
        layout.label(text="Exact Si JSON: 25 materials / 61 PNG",icon='INFO')
        layout.label(text="FX may use MainTex, masks, UV motion")
        layout.label(text="Audited automatically after successful AE Build")
        status = str(context.scene.get('SaberShader_AE_SourceAudit_LastStatus', '') or '')
        if status:
            layout.label(text="Last auto audit: " + status[:32])
            layout.label(text="FX needing review: %s" % context.scene.get('SaberShader_AE_SourceAudit_LastFXUnbound', 0))
        layout.operator('sabershader.ae_si_source_dictionary_audit',text='Audit Si Sources (Read Only)',icon='TEXT')
        layout.label(text="Report path shown in operator feedback")
        fx_status = str(context.scene.get('SaberShader_AE_SiFX_E3_Status', '') or '')
        if fx_status:
            layout.label(text='FX source materials: ' + fx_status[:25])
            layout.label(text='Materials: %s' % context.scene.get('SaberShader_AE_SiFX_E3_Materials', 0))
        e31_status = str(context.scene.get('SaberShader_AE_SiFX_E31_Status', '') or '')
        if e31_status:
            layout.label(text='FX opacity: ' + e31_status[:27])
            layout.label(text='Calibrated: %s | Preserved: %s' % (
                context.scene.get('SaberShader_AE_SiFX_E31_Calibrated', 0),
                context.scene.get('SaberShader_AE_SiFX_E31_Skipped', 0)))
        vfx_status = str(context.scene.get('SaberShader_AE_SiVFX_E31_Status', '') or '')
        if vfx_status:
            layout.label(text='VFX placeholders: %s (unverified)' %
                         context.scene.get('SaberShader_AE_SiVFX_E31_Recognized', 0))
        status32 = str(context.scene.get('SaberShader_AE_SiVFX_E32_Status', '') or '')
        if status32:
            layout.label(text='VFX preview: ' + status32[:27])
            layout.label(text='Previewed VFX meshes: %s' % context.scene.get('SaberShader_AE_SiVFX_E32_Applied', 0))
        status331 = str(context.scene.get('SaberShader_AE_SiFX_E331_Status', '') or '')
        if status331:
            layout.label(text='Dual-layer FX: ' + status331[:25])
            layout.label(text='FX: %s | VFX: %s' % (
                context.scene.get('SaberShader_AE_SiFX_E331_FX', 0),
                context.scene.get('SaberShader_AE_SiFX_E331_VFX', 0)))
            layout.label(text='VFX migrated to B: %s' % context.scene.get('SaberShader_AE_SiFX_E332_VFXB_Upgraded', 0))
        layout.label(text='Dual-layer VFX preview: maximum 23% alpha')
        ab_rows = [o for o in context.scene.objects if o.name.startswith('S_actor_jsspsi_vfxpart_') and
                   o.get('SaberShader_AE_Si_E341_AB_Token', '')]
        study = layout.box()
        study.label(text='Si Idle Ink Comparison', icon='SHADING_TEXTURE')
        study.label(text='Manual A/B study is separate from automatic Build A')
        from . import ae_fx_auto_appearance as build_a
        auto_state = build_a.status(context)
        if auto_state == 'ACTIVE':
            study.label(text='Build A: ACTIVE (7 Si meshes)', icon='CHECKMARK')
            if not ab_rows:
                study.operator('sabershader.si_build_a_restore', text='Restore Pre-A Si VFX', icon='LOOP_BACK')
        elif auto_state == 'SUSPENDED':
            study.label(text='Build A: SUSPENDED; Build unavailable', icon='ERROR')
            study.operator('sabershader.si_build_a_resume', text='Recover Suspended A', icon='FILE_REFRESH')
        elif auto_state != 'NONE':
            study.label(text='Build A: ' + auto_state + ' (inspect before Build)', icon='ERROR')
        else:
            study.label(text='Main Build applies A for verified Si when eligible')
        if ab_rows:
            study.label(text='Active A/B session: %d/7 meshes' % len(ab_rows))
            study.label(text='Showing: ' + str(ab_rows[0].get('SaberShader_AE_Si_E341_AB_Current','UNKNOWN')))
            row = study.row(align=True)
            row.operator('sabershader.si_vfx_ab_show_a', text='Show A')
            row.operator('sabershader.si_vfx_ab_show_b', text='Show B')
            study.operator('sabershader.si_vfx_ab_snapshot', text='Record A/B Metadata (Read Only)', icon='TEXT')
            study.operator('sabershader.si_vfx_ab_restore', text='Restore Original (A/B)', icon='LOOP_BACK')
            study.label(text='Build blocked until original is restored', icon='INFO')
        else:
            study.operator('sabershader.si_vfx_ab_prepare', text='Prepare A/B from Current Si', icon='DUPLICATE')
            study.label(text='A=Mask if present; else Single Trail approximation')
            study.label(text='B=Dual Layer, gfx18 primary')
        qa_status = str(context.scene.get('SaberShader_AE_Si_E332QA_Status', '') or '')
        if qa_status:
            layout.label(text='AE Si VFX native topology: ' + qa_status[:15], icon='CHECKMARK' if qa_status == 'PASS' else 'INFO')
            layout.label(text='QA checks: native restore/save tests remain manual')
        if auto_state == 'ACTIVE':
            layout.label(text='Dual-layer comparison checked before final Build appearance')
            layout.label(text='Restore Pre-A to inspect B manually')
        else:
            layout.operator('sabershader.ae_si_fx_e332_validate',
                            text='Inspect Si FX Materials (Read Only)', icon='TEXT')
        layout.operator('sabershader.ae_si_fx_e331_restore',
                        text='Restore Si FX Appearance', icon='LOOP_BACK')
        layout.label(text='VFX/FX preview approximate, NOT a Unity shader')
        layout.operator('sabershader.ae_si_vfx_e32_restore', text='Restore VFX Placeholder Materials', icon='LOOP_BACK')
        layout.operator('sabershader.ae_si_fx_e31_restore_opacity',
                        text='Restore E3 FX Opacity (Advanced)', icon='LOOP_BACK')
        layout.operator('sabershader.ae_si_fx_e3_restore', text='Restore Si FX (Advanced)', icon='LOOP_BACK')
        layout.label(text="Audit only is read-only; E3 shader preview via main Build")
