import bpy

from .fmt_3dan import Export3DAN
from .fmt_cad import ImportCADOperator
from .fmt_3dg1 import Export3DG1, Import3DGI
from .fmt_asm import ExportAnimatedToASM, ExportToBSP, ExportToBSPTreeless, ExportToGZS, ImportBSPOperator
from .slopes import ExportSlopeData

# FastFX
# File: menus.py
# Functions setting up menu options for import/export.
# Copyright (c) 2026 Sunlit
# Released under the MIT License.

# =========================
# ASM Export Submenus
# =========================
class TOPBAR_MT_fastfx_asm(bpy.types.Menu):
    bl_idname = "TOPBAR_MT_fastfx_asm"
    bl_label = "Star Fox ASM"

    def draw(self, context):
        self.layout.operator(ExportToBSP.bl_idname, text="Star Fox ASM BSP (.asm/.bsp)")
        self.layout.operator(ExportToBSPTreeless.bl_idname, text="Star Fox ASM BSP (treeless) (.asm/.bsp)")
        self.layout.operator(ExportToGZS.bl_idname, text="Star Fox ASM GZS (.asm/.gzs)")


class TOPBAR_MT_fastfx_asm_animated(bpy.types.Menu):
    bl_idname = "TOPBAR_MT_fastfx_asm_animated"
    bl_label = "Star Fox ASM (Animated)"

    def draw(self, context):
        operator = self.layout.operator(ExportAnimatedToASM.bl_idname, text="Star Fox ASM BSP (.asm/.bsp)")
        operator.output_format = 'bsp'
        operator = self.layout.operator(ExportAnimatedToASM.bl_idname, text="Star Fox ASM BSP (treeless) (.asm/.bsp)")
        operator.output_format = 'bsp_treeless'
        operator = self.layout.operator(ExportAnimatedToASM.bl_idname, text="Star Fox ASM GZS (.asm/.gzs)")
        operator.output_format = 'gzs'

# =========================
# Slope Data Export Submenu
# =========================
class TOPBAR_MT_fastfx_slopes(bpy.types.Menu):
    bl_idname = "TOPBAR_MT_fastfx_slopes"
    bl_label = "Star Fox 2 Slope Data"

    def draw(self, context):
        if context.scene.fastfx_game_preset != "STARFOX2":
            return
        operator = self.layout.operator(
            ExportSlopeData.bl_idname,
            text="Static Slope Data (.asm/.slo)",
        )
        operator.animated = False
        operator = self.layout.operator(
            ExportSlopeData.bl_idname,
            text="Animated Slope Data (.asm/.slo)",
        )
        operator.animated = True


# =========================
# Menu Functions
# =========================
def menu_func_import(self, context):
    self.layout.operator(Import3DGI.bl_idname, text="3DG1/3DGI/3DAN/Fundoshi-kun (.txt/.3dg1/.anm/.3dan/.obj/.3dgi)")
    self.layout.operator(ImportCADOperator.bl_idname, text="Iwamoto CAD/NCA (.cad/.nca)")
    self.layout.operator(ImportBSPOperator.bl_idname, text="Star Fox ASM BSP/GZS (.asm/.bsp/.gzs)")

def menu_func_export(self, context):
    self.layout.operator(Export3DG1.bl_idname, text="3DG1/3DGI/Fundoshi-kun (.txt/.3dg1/.obj)")
    self.layout.operator(Export3DAN.bl_idname, text="3DAN/3DGI/Animated Fundoshi-kun (.anm)")
    self.layout.menu(TOPBAR_MT_fastfx_asm.bl_idname, text=TOPBAR_MT_fastfx_asm.bl_label)
    self.layout.menu(TOPBAR_MT_fastfx_asm_animated.bl_idname, text=TOPBAR_MT_fastfx_asm_animated.bl_label)
    if context.scene.fastfx_game_preset == "STARFOX2":
        self.layout.menu(TOPBAR_MT_fastfx_slopes.bl_idname, text=TOPBAR_MT_fastfx_slopes.bl_label)
