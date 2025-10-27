"""
Main module: Design of Compression Member
Sub-module:  Design of column (loaded axially)

@author: Rutvik Joshi, N swaroop, Adnan Abdullah (Project interns, 2021)
         Danish Ansari

Reference:
    IS 800: 2007 General construction in steel - Code of practice (Third revision)
"""

import logging
import math
import sys
import os
from typing import Dict, List, Tuple, Optional, Any

import numpy as np

from ...Common import *
from ..connection.moment_connection import MomentConnection
from ...utils.common.material import *
from ...utils.common.load import Load
from ...utils.common.component import ISection, Material
from ...utils.common.component import *
from ..member import Member
from ...Report_functions import *
from ...design_report.reportGenerator_latex import CreateLatex
from pylatex.utils import NoEscape


# ============================================================================
# CONSTANTS
# ============================================================================
SAFETY_FACTORS = {
    'gamma_m0': IS800_2007.cl_5_4_1_Table_5["gamma_m0"]["yielding"]
}

EPSILON_FACTOR = 250
DEFAULT_VALUES = {
    'allowable_ur': 1.0,
    'effective_area_factor': 1.0,
    'steel_cost_per_kg': 50,
    'optimization_parameter': 'Utilization Ratio'
}

SECTION_CLASSES = ['Plastic', 'Compact', 'Semi-Compact', 'Slender']


# ============================================================================
# LOGGER SETUP
# ============================================================================
logger = logging.getLogger('Osdag')


def setup_logger(key=None):
    """Set up and configure logger for Column Design Module."""
    logger.setLevel(logging.DEBUG)
    
    # Console handler
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # File handler
    file_handler = logging.FileHandler('logging_text.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Custom handler if key provided
    if key is not None:
        custom_handler = OurLog(key)
        custom_handler.setFormatter(formatter)
        logger.addHandler(custom_handler)


# ============================================================================
# HELPER CLASSES
# ============================================================================
class SectionProperties:
    """Encapsulates section property fetching logic."""
    
    @staticmethod
    def get_section_property(sec_profile: str, designation: str, material: str):
        """
        Fetch section properties based on profile type.
        
        Args:
            sec_profile: Type of section profile
            designation: Section designation
            material: Material grade
            
        Returns:
            Section property object
        """
        if sec_profile == VALUES_SEC_PROFILE[0]:  # Beams and columns
            try:
                return Beam(designation=designation, material_grade=material)
            except:
                return Column(designation=designation, material_grade=material)
                
        elif sec_profile == VALUES_SEC_PROFILE[1]:  # RHS and SHS
            try:
                return RHS(designation=designation, material_grade=material)
            except:
                return SHS(designation=designation, material_grade=material)
                
        elif sec_profile == VALUES_SEC_PROFILE[2]:  # CHS
            return CHS(designation=designation, material_grade=material)
        else:
            return Column(designation=designation, material_grade=material)


class SectionClassifier:
    """Handles section classification based on IS 800:2007 Table 2."""
    
    def __init__(self, material_property):
        self.material_property = material_property
        self.epsilon = math.sqrt(EPSILON_FACTOR / material_property.fy)
    
    def classify_section(self, sec_profile: str, section_property) -> Dict[str, Any]:
        """
        Classify section into Plastic/Compact/Semi-Compact/Slender.
        
        Returns:
            Dictionary with classification details
        """
        if sec_profile == VALUES_SEC_PROFILE[0]:  # Beams and Columns
            return self._classify_i_section(section_property)
        elif sec_profile == VALUES_SEC_PROFILE[1]:  # RHS and SHS
            return self._classify_hollow_section(section_property)
        elif sec_profile == VALUES_SEC_PROFILE[2]:  # CHS
            return self._classify_circular_section(section_property)
        
        return {}
    
    def _classify_i_section(self, section_property) -> Dict[str, Any]:
        """Classify I-section."""
        if section_property.type == 'Rolled':
            flange_class = IS800_2007.Table2_i(
                section_property.flange_width / 2,
                section_property.flange_thickness,
                self.material_property.fy,
                section_property.type
            )[0]
        else:
            flange_class = IS800_2007.Table2_i(
                (section_property.flange_width / 2) - (section_property.web_thickness / 2),
                section_property.flange_thickness,
                section_property.fy,
                section_property.type
            )[0]
        
        web_class = IS800_2007.Table2_iii(
            section_property.depth - (2 * section_property.flange_thickness),
            section_property.web_thickness,
            self.material_property.fy,
            classification_type='Axial compression'
        )
        
        web_ratio = (section_property.depth - 2 * (
            section_property.flange_thickness + section_property.root_radius
        )) / section_property.web_thickness
        
        flange_ratio = section_property.flange_width / 2 / section_property.flange_thickness
        
        return {
            'flange_class': flange_class,
            'web_class': web_class,
            'flange_ratio': flange_ratio,
            'web_ratio': web_ratio
        }
    
    def _classify_hollow_section(self, section_property) -> Dict[str, Any]:
        """Classify RHS/SHS section."""
        flange_class = IS800_2007.Table2_iii(
            section_property.depth - (2 * section_property.flange_thickness),
            section_property.flange_thickness,
            self.material_property.fy,
            classification_type='Axial compression'
        )
        
        web_ratio = (section_property.depth - 2 * (
            section_property.flange_thickness + section_property.root_radius
        )) / section_property.web_thickness
        
        flange_ratio = section_property.flange_width / 2 / section_property.flange_thickness
        
        return {
            'flange_class': flange_class,
            'web_class': flange_class,
            'flange_ratio': flange_ratio,
            'web_ratio': web_ratio
        }
    
    def _classify_circular_section(self, section_property) -> Dict[str, Any]:
        """Classify CHS section."""
        flange_class = IS800_2007.Table2_x(
            section_property.out_diameter,
            section_property.flange_thickness,
            self.material_property.fy,
            load_type='axial compression'
        )
        
        web_ratio = (section_property.depth - 2 * (
            section_property.flange_thickness + section_property.root_radius
        )) / section_property.web_thickness
        
        flange_ratio = section_property.flange_width / 2 / section_property.flange_thickness
        
        return {
            'flange_class': flange_class,
            'web_class': flange_class,
            'flange_ratio': flange_ratio,
            'web_ratio': web_ratio
        }
    
    @staticmethod
    def determine_overall_class(flange_class: str, web_class: str) -> str:
        """Determine overall section class from flange and web classes."""
        if flange_class == 'Slender' or web_class == 'Slender':
            return 'Slender'
        elif flange_class == 'Semi-Compact' or web_class == 'Semi-Compact':
            return 'Semi-Compact'
        elif flange_class == 'Compact' or web_class == 'Compact':
            return 'Compact'
        else:
            return 'Plastic'


class BucklingCalculator:
    """Handles buckling-related calculations."""
    
    def __init__(self, material_property, gamma_m0: float):
        self.material_property = material_property
        self.gamma_m0 = gamma_m0
    
    def calculate_buckling_parameters(
        self,
        section_property,
        effective_length: float,
        axis: str = 'z'
    ) -> Dict[str, float]:
        """
        Calculate all buckling parameters for given axis.
        
        Args:
            section_property: Section properties object
            effective_length: Effective length in mm
            axis: 'z' or 'y'
            
        Returns:
            Dictionary with buckling parameters
        """
        # Get radius of gyration
        if axis == 'z':
            rad_of_gy = section_property.rad_of_gy_z
        else:
            rad_of_gy = section_property.rad_of_gy_y
        
        # Effective slenderness ratio
        effective_sr = effective_length / rad_of_gy
        
        # Euler buckling stress
        euler_bs = (math.pi ** 2 * section_property.modulus_of_elasticity) / (effective_sr ** 2)
        
        # Non-dimensional effective slenderness ratio
        non_dim_eff_sr = math.sqrt(self.material_property.fy / euler_bs)
        
        return {
            'effective_sr': effective_sr,
            'euler_bs': euler_bs,
            'non_dim_eff_sr': non_dim_eff_sr
        }
    
    def calculate_design_compressive_stress(
        self,
        imperfection_factor: float,
        non_dim_eff_sr: float
    ) -> Dict[str, float]:
        """
        Calculate design compressive stress.
        
        Returns:
            Dictionary with phi, stress reduction factor, and fcd
        """
        # Calculate phi
        phi = 0.5 * (1 + (imperfection_factor * (non_dim_eff_sr - 0.2)) + non_dim_eff_sr ** 2)
        
        # Stress reduction factor
        srf = 1 / (phi + math.sqrt(phi ** 2 - non_dim_eff_sr ** 2))
        
        # Design compressive stress
        fcd_1 = (srf * self.material_property.fy) / self.gamma_m0
        fcd_2 = self.material_property.fy / self.gamma_m0
        
        return {
            'phi': phi,
            'srf': srf,
            'fcd_1': fcd_1,
            'fcd_2': fcd_2,
            'fcd': min(fcd_1, fcd_2)
        }


class EffectiveAreaCalculator:
    """Calculates effective sectional area."""
    
    @staticmethod
    def calculate(
        section_class: str,
        sec_profile: str,
        section_property,
        epsilon: float,
        area_factor: float = 1.0
    ) -> float:
        """
        Calculate effective sectional area.
        
        Args:
            section_class: Classification of section
            sec_profile: Type of section profile
            section_property: Section properties object
            epsilon: Epsilon factor
            area_factor: Area reduction factor
            
        Returns:
            Effective area in mm²
        """
        if section_class == 'Slender':
            if sec_profile == VALUES_SEC_PROFILE[0]:  # Beams and Columns
                effective_area = (
                    2 * ((31.4 * epsilon * section_property.flange_thickness) * 
                         section_property.flange_thickness) +
                    2 * ((21 * epsilon * section_property.web_thickness) * 
                         section_property.web_thickness)
                )
            elif sec_profile == VALUES_SEC_PROFILE[1]:  # RHS and SHS
                effective_area = (2 * 21 * epsilon * section_property.flange_thickness) * 2
            else:
                effective_area = section_property.area
        else:
            effective_area = section_property.area
        
        return round(effective_area * area_factor, 2)


# ============================================================================
# MAIN CLASS
# ============================================================================
class ColumnDesign(Member):
    """Main class for column design calculations."""
    
    def __init__(self):
        super(ColumnDesign, self).__init__()
        self._initialize_attributes()
        
    def cleanup(self):
        """Clean up logger handlers when module is closed."""
        # Remove all handlers associated with this module
        for handler in logger.handlers[:]:
            try:
                handler.close()
                logger.removeHandler(handler)
            except:
                pass
    
    def _initialize_attributes(self):
        """Initialize all class attributes."""
        # Design status tracking
        self.design_status = False
        self.design_status_list = []
        self.failed_design_dict = {}
        
        # Section properties
        self.input_section_list = []
        self.input_section_classification = {}
        
        # Results storage
        self.optimum_section_ur_results = {}
        self.optimum_section_ur = []
        self.optimum_section_cost_results = {}
        self.optimum_section_cost = []
    
    # ========================================================================
    # DESIGN PREFERENCE METHODS
    # ========================================================================
    
    def tab_list(self) -> List[Tuple]:
        """Return list of tabs for design preferences."""
        return [
            (KEY_DISP_COLSEC, TYPE_TAB_1, self.tab_section),
            ("Optimization", TYPE_TAB_2, self.optimization_tab_column_design),
            ("Design", TYPE_TAB_2, self.design_values),
        ]
    
    def tab_value_changed(self) -> List[Tuple]:
        """Return list of dependent value changes in design preferences."""
        return [
            (KEY_DISP_COLSEC, [KEY_SEC_MATERIAL], [KEY_SEC_FU, KEY_SEC_FY], 
             TYPE_TEXTBOX, self.get_fu_fy_I_section),
            (KEY_DISP_COLSEC, ['Label_1', 'Label_2', 'Label_3', 'Label_4', 'Label_5'],
             ['Label_11', 'Label_12', 'Label_13', 'Label_14', 'Label_15', 'Label_16', 
              'Label_17', 'Label_18', 'Label_19', 'Label_20', 'Label_21', 'Label_22', KEY_IMAGE],
             TYPE_TEXTBOX, self.get_I_sec_properties),
            (KEY_DISP_COLSEC, ['Label_HS_1', 'Label_HS_2', 'Label_HS_3'],
             ['Label_HS_11', 'Label_HS_12', 'Label_HS_13', 'Label_HS_14', 'Label_HS_15',
              'Label_HS_16', 'Label_HS_17', 'Label_HS_18', 'Label_HS_19', 'Label_HS_20',
              'Label_HS_21', 'Label_HS_22', KEY_IMAGE],
             TYPE_TEXTBOX, self.get_SHS_RHS_properties),
            (KEY_DISP_COLSEC, ['Label_CHS_1', 'Label_CHS_2', 'Label_CHS_3'],
             ['Label_CHS_11', 'Label_CHS_12', 'Label_CHS_13', 'Label_HS_14', 'Label_HS_15',
              'Label_HS_16', 'Label_21', 'Label_22', KEY_IMAGE],
             TYPE_TEXTBOX, self.get_CHS_properties),
            (KEY_DISP_COLSEC, [KEY_SECSIZE], [KEY_SOURCE], 
             TYPE_TEXTBOX, self.change_source),
        ]
    
    def edit_tabs(self) -> List:
        """Return list for tab editing (empty for this module)."""
        return []
    
    def input_dictionary_design_pref(self) -> List[Tuple]:
        """Return design preference keys to save."""
        return [
            (KEY_DISP_COLSEC, TYPE_COMBOBOX, [KEY_SEC_MATERIAL]),
            (KEY_DISP_COLSEC, TYPE_TEXTBOX, [KEY_SEC_FU, KEY_SEC_FY]),
            ("Optimization", TYPE_TEXTBOX, [KEY_ALLOW_UR, KEY_EFFECTIVE_AREA_PARA]),
            ("Design", TYPE_COMBOBOX, [KEY_DP_DESIGN_METHOD]),
        ]
    
    def input_dictionary_without_design_pref(self) -> List[Tuple]:
        """Return default design preference values."""
        return [
            (KEY_MATERIAL, [KEY_SEC_MATERIAL], 'Input Dock'),
            (None, [KEY_ALLOW_UR, KEY_EFFECTIVE_AREA_PARA, KEY_DP_DESIGN_METHOD], ''),
        ]
    
    def refresh_input_dock(self) -> List[Tuple]:
        """Return keys to refresh in input dock."""
        return [
            (KEY_DISP_COLSEC, KEY_SECSIZE, TYPE_COMBOBOX, KEY_SECSIZE, None, None, "Columns"),
        ]
    
    def get_values_for_design_pref(self, key: str, design_dictionary: Dict) -> str:
        """Get default values for design preferences."""
        return DEFAULT_VALUES.get(key.lower().replace('.', '_'), '')
    
    # ========================================================================
    # INPUT/OUTPUT METHODS
    # ========================================================================
    
    def module_name(self) -> str:
        """Return module name."""
        return KEY_DISP_COMPRESSION_COLUMN
    
    @staticmethod
    def set_osdaglogger(key):
        """Set logger for Column Design Module."""
        setup_logger(key)
    
    def customized_input(self) -> List[Tuple]:
        """Return customized input functions."""
        return [(KEY_SECSIZE, self.fn_profile_section)]
    
    def input_values(self) -> List[Tuple]:
        """Return input dock configuration."""
        self.module = KEY_DISP_COMPRESSION_COLUMN
        
        return [
            (None, KEY_SECTION_PROPERTY, TYPE_TITLE, None, True, 'No Validator'),
            (KEY_MODULE, KEY_DISP_COMPRESSION_COLUMN, TYPE_MODULE, None, True, 'No Validator'),
            (KEY_SEC_PROFILE, KEY_DISP_SEC_PROFILE, TYPE_COMBOBOX, VALUES_SEC_PROFILE, True, 'No Validator'),
            (KEY_SECSIZE, KEY_DISP_SECSIZE, TYPE_COMBOBOX_CUSTOMIZED, ['All', 'Customized'], True, 'No Validator'),
            (KEY_MATERIAL, KEY_DISP_MATERIAL, TYPE_COMBOBOX, VALUES_MATERIAL, True, 'No Validator'),
            (None, KEY_SECTION_DATA, TYPE_TITLE, None, True, 'No Validator'),
            (KEY_UNSUPPORTED_LEN_ZZ, KEY_DISP_UNSUPPORTED_LEN_ZZ, TYPE_TEXTBOX, None, True, 'Int Validator'),
            (KEY_UNSUPPORTED_LEN_YY, KEY_DISP_UNSUPPORTED_LEN_YY, TYPE_TEXTBOX, None, True, 'Int Validator'),
            (None, KEY_DISP_END_CONDITION, TYPE_TITLE, None, True, 'No Validator'),
            (KEY_END1, KEY_DISP_END1, TYPE_COMBOBOX, VALUES_END1, True, 'No Validator'),
            (KEY_END2, KEY_DISP_END2, TYPE_COMBOBOX, VALUES_END2, True, 'No Validator'),
            (KEY_IMAGE, None, TYPE_IMAGE_COMPRESSION, 
             str(files("osdag_core.data.ResourceFiles.images").joinpath("6.RRRR.PNG")), True, 'No Validator'),
            (None, KEY_DISP_END_CONDITION_2, TYPE_TITLE, None, True, 'No Validator'),
            (KEY_END1_Y, KEY_DISP_END1_Y, TYPE_COMBOBOX, VALUES_END1_Y, True, 'No Validator'),
            (KEY_END2_Y, KEY_DISP_END2_Y, TYPE_COMBOBOX, VALUES_END2_Y, True, 'No Validator'),
            (KEY_IMAGE_Y, None, TYPE_IMAGE_COMPRESSION,
             str(files("osdag_core.data.ResourceFiles.images").joinpath("6.RRRR.PNG")), True, 'No Validator'),
            (None, DISP_TITLE_FSL, TYPE_TITLE, None, True, 'No Validator'),
            (KEY_AXIAL, KEY_DISP_AXIAL_STAR, TYPE_TEXTBOX, None, True, 'Int Validator'),
        ]
    
    def fn_profile_section(self):
        """Return section list based on profile."""
        profile = self[0]
        
        if profile == 'Beams and Columns':
            res1 = connectdb("Beams", call_type="popup")
            res2 = connectdb("Columns", call_type="popup")
            return list(set(res1 + res2))
        elif profile == 'RHS and SHS':
            res1 = connectdb("RHS", call_type="popup")
            res2 = connectdb("SHS", call_type="popup")
            return list(set(res1 + res2))
        elif profile == 'CHS':
            return connectdb("CHS", call_type="popup")
        elif profile in ['Angles', 'Back to Back Angles', 'Star Angles']:
            return connectdb('Angles', call_type="popup")
        elif profile in ['Channels', 'Back to Back Channels']:
            return connectdb("Channels", call_type="popup")
        
        return []
    
    def fn_end1_end2(self):
        """Return valid end2 options based on end1."""
        end1 = self[0]
        
        end_conditions = {
            'Fixed': VALUES_END2,
            'Free': ['Fixed'],
            'Hinged': ['Fixed', 'Hinged', 'Roller'],
            'Roller': ['Fixed', 'Hinged']
        }
        
        return end_conditions.get(end1, [])
    
    def fn_end1_image(self):
        """Return image path based on end1 condition."""
        image_map = {
            'Fixed': "6.RRRR.PNG",
            'Free': "1.RRFF.PNG",
            'Hinged': "5.RRRF.PNG",
            'Roller': "4.RRFR.PNG"
        }
        
        image_file = image_map.get(self, "6.RRRR.PNG")
        return str(files("osdag_core.data.ResourceFiles.images").joinpath(image_file))
    
    def fn_end2_image(self):
        """Return image path based on end1 and end2 conditions."""
        end1, end2 = self[0], self[1]
        
        image_map = {
            ('Fixed', 'Fixed'): "6.RRRR.PNG",
            ('Fixed', 'Free'): "1.RRFF_rotated.PNG",
            ('Fixed', 'Hinged'): "5.RRRF_rotated.PNG",
            ('Fixed', 'Roller'): "4.RRFR_rotated.PNG",
            ('Free', 'Fixed'): "1.RRFF.PNG",
            ('Hinged', 'Fixed'): "5.RRRF.PNG",
            ('Hinged', 'Hinged'): "3.RFRF.PNG",
            ('Hinged', 'Roller'): "2.FRFR_rotated.PNG",
            ('Roller', 'Fixed'): "4.RRFR.PNG",
            ('Roller', 'Hinged'): "2.FRFR.PNG",
        }
        
        image_file = image_map.get((end1, end2), "6.RRRR.PNG")
        return str(files("osdag_core.data.ResourceFiles.images").joinpath(image_file))
    
    def input_value_changed(self) -> List[Tuple]:
        """Return list of dynamic input changes."""
        return [
            ([KEY_SEC_PROFILE], KEY_SECSIZE, TYPE_COMBOBOX_CUSTOMIZED, self.fn_profile_section),
            ([KEY_END1], KEY_END2, TYPE_COMBOBOX, self.fn_end1_end2),
            ([KEY_END1, KEY_END2], KEY_IMAGE, TYPE_IMAGE, self.fn_end2_image),
            ([KEY_END1_Y], KEY_END2_Y, TYPE_COMBOBOX, self.fn_end1_end2),
            ([KEY_END1_Y, KEY_END2_Y], KEY_IMAGE_Y, TYPE_IMAGE, self.fn_end2_image),
            ([KEY_MATERIAL], KEY_MATERIAL, TYPE_CUSTOM_MATERIAL, self.new_material),
        ]
    
    def output_values(self, flag: bool) -> List[Tuple]:
        """Return output dock configuration."""
        return [
            (None, DISP_TITLE_OPTIMUM_SECTION, TYPE_TITLE, None, True),
            (KEY_TITLE_OPTIMUM_DESIGNATION, KEY_DISP_TITLE_OPTIMUM_DESIGNATION, TYPE_TEXTBOX,
             self.result_designation if flag else '', True),
            (KEY_OPTIMUM_UR_COMPRESSION, KEY_DISP_OPTIMUM_UR_COMPRESSION, TYPE_TEXTBOX,
             self.result_UR if flag else '', True),
            (KEY_OPTIMUM_SC, KEY_DISP_OPTIMUM_SC, TYPE_TEXTBOX,
             self.result_section_class if flag else '', True),
            (KEY_EFF_SEC_AREA_ZZ, KEY_DISP_EFF_SEC_AREA_ZZ, TYPE_TEXTBOX,
             round(self.result_effective_area, 2) if flag else '', True),
            (None, DISP_TITLE_ZZ, TYPE_TITLE, None, True),
            (KEY_EFF_LEN_ZZ, KEY_DISP_EFF_LEN_ZZ, TYPE_TEXTBOX,
             round(self.result_eff_len_zz * 1e-3, 2) if flag else '', True),
            (KEY_EULER_BUCKLING_STRESS_ZZ, KEY_DISP_EULER_BUCKLING_STRESS_ZZ, TYPE_TEXTBOX,
             round(self.result_ebs_zz, 2) if flag else '', True),
            (KEY_BUCKLING_CURVE_ZZ, KEY_DISP_BUCKLING_CURVE_ZZ, TYPE_TEXTBOX,
             self.result_bc_zz if flag else '', True),
            (KEY_IMPERFECTION_FACTOR_ZZ, KEY_DISP_IMPERFECTION_FACTOR_ZZ, TYPE_TEXTBOX,
             round(self.result_IF_zz, 2) if flag else '', True),
            (KEY_SR_FACTOR_ZZ, KEY_DISP_SR_FACTOR_ZZ, TYPE_TEXTBOX,
             round(self.result_srf_zz, 2) if flag else '', True),
            (KEY_NON_DIM_ESR_ZZ, KEY_DISP_NON_DIM_ESR_ZZ, TYPE_TEXTBOX,
             round(self.result_nd_esr_zz, 2) if flag else '', True),
            (KEY_COMP_STRESS_ZZ, KEY_DISP_COMP_STRESS_ZZ, TYPE_TEXTBOX,
             round(self.result_fcd_1_zz, 2) if flag else '', True),
            (None, DISP_TITLE_YY, TYPE_TITLE, None, True),
            (KEY_EFF_LEN_YY, KEY_DISP_EFF_LEN_YY, TYPE_TEXTBOX,
             round(self.result_eff_len_yy * 1e-3, 2) if flag else '', True),
            (KEY_EULER_BUCKLING_STRESS_YY, KEY_DISP_EULER_BUCKLING_STRESS_YY, TYPE_TEXTBOX,
             round(self.result_ebs_yy, 2) if flag else '', True),
            (KEY_BUCKLING_CURVE_YY, KEY_DISP_BUCKLING_CURVE_YY, TYPE_TEXTBOX,
             self.result_bc_yy if flag else '', True),
            (KEY_IMPERFECTION_FACTOR_YY, KEY_DISP_IMPERFECTION_FACTOR_YY, TYPE_TEXTBOX,
             round(self.result_IF_yy, 2) if flag else '', True),
            (KEY_SR_FACTOR_YY, KEY_DISP_SR_FACTOR_YY, TYPE_TEXTBOX,
             round(self.result_srf_yy, 2) if flag else '', True),
            (KEY_NON_DIM_ESR_YY, KEY_DISP_NON_DIM_ESR_YY, TYPE_TEXTBOX,
             round(self.result_nd_esr_yy, 2) if flag else '', True),
            (KEY_COMP_STRESS_YY, KEY_DISP_COMP_STRESS_YY, TYPE_TEXTBOX,
             round(self.result_fcd_1_yy, 2) if flag else '', True),
            (None, KEY_DESIGN_COMPRESSION, TYPE_TITLE, None, True),
            (KEY_MIN_DESIGN_COMP_STRESS, KEY_MIN_DESIGN_COMP_STRESS_VAL, TYPE_TEXTBOX,
             round(min(self.result_fcd_1_yy, self.result_fcd_1_zz), 2) if flag else '', True),
            (KEY_MAT_STRESS, KEY_DISP_MAT_STRESS, TYPE_TEXTBOX,
             round(self.f_cd_2, 2) if flag else '', True),
            (KEY_FCD, KEY_DISP_FCD, TYPE_TEXTBOX,
             round(self.result_fcd, 2) if flag else '', True),
            (KEY_DESIGN_STRENGTH_COMPRESSION, KEY_DISP_DESIGN_STRENGTH_COMPRESSION, TYPE_TEXTBOX,
             round(self.result_capacity * 1e-3, 2) if flag else '', True),
        ]
    
    # ========================================================================
    # VALIDATION AND INPUT PROCESSING
    # ========================================================================
    
    def func_for_validation(self, design_dictionary: Dict) -> Optional[List[str]]:
        """
        Validate input values and initiate design if valid.
        
        Args:
            design_dictionary: Dictionary containing all input values
            
        Returns:
            List of error messages if validation fails, None otherwise
        """
        all_errors = []
        self.design_status = False
        missing_fields = self._check_missing_fields(design_dictionary)
        
        if missing_fields:
            error = self.generate_missing_fields_error_string(self, missing_fields)
            all_errors.append(error)
            return all_errors
        
        # All fields present, proceed with design
        self.set_input_values(self, design_dictionary)
        
        if not self.design_status and len(self.failed_design_dict) > 0:
            logger.error("Design Failed, Check Design Report")
            return
        elif not self.design_status:
            logger.error("Design Failed. Slender Sections Selected")
            return
        
        return None
    
    def _check_missing_fields(self, design_dictionary: Dict) -> List[str]:
        """Check for missing or invalid input fields."""
        missing_fields = []
        option_list = self.input_values(self)
        
        for option in option_list:
            if option[2] == TYPE_TEXTBOX:
                if design_dictionary.get(option[0]) == '':
                    missing_fields.append(option[1])
            elif option[2] == TYPE_COMBOBOX and option[0] not in [
                KEY_SEC_PROFILE, KEY_END1, KEY_END2, KEY_END1_Y, KEY_END2_Y
            ]:
                val = option[3]
                if design_dictionary.get(option[0]) == val[0]:
                    missing_fields.append(option[1])
        
        return missing_fields
    
    def get_3d_components(self) -> List[Tuple]:
        """Return 3D component definitions."""
        return [('Model', self.call_3DModel)]
    
    def warn_text(self):
        """Log warning if deprecated section is selected."""
        red_list = red_list_function()
        
        if self.sec_profile == VALUES_SEC_PROFILE[0]:  # Beams and Columns
            for section in self.sec_list:
                if section in red_list:
                    logger.warning(
                        f"You are using a section ({section}) (in red color) that is not "
                        f"available in latest version of IS 808"
                    )
    
    # ========================================================================
    # MAIN DESIGN METHODS
    # ========================================================================
    
    def set_input_values(self, design_dictionary: Dict):
        """Set input values from design dictionary and initiate design."""
        super(ColumnDesign, self).set_input_values(self, design_dictionary)
        
        # Extract inputs
        self._extract_inputs(design_dictionary)
        
        # Initialize material and safety factors
        self.gamma_m0 = SAFETY_FACTORS['gamma_m0']
        self.material_property = Material(material_grade=self.material, thickness=0)
        
        # Validate design preferences
        self._validate_design_preferences()
        
        # Perform design
        self._initialize_attributes()
        flag = self.section_classification(self)
        
        if flag:
            self.design_column(self)
            self.results(self)
    
    def _extract_inputs(self, design_dictionary: Dict):
        """Extract all inputs from design dictionary."""
        # Section properties
        self.module = design_dictionary[KEY_MODULE]
        self.mainmodule = 'Columns with known support conditions'
        self.sec_profile = design_dictionary[KEY_SEC_PROFILE]
        self.sec_list = design_dictionary[KEY_SECSIZE]
        self.material = design_dictionary[KEY_SEC_MATERIAL]
        
        # Section user data
        self.length_zz = float(design_dictionary[KEY_UNSUPPORTED_LEN_ZZ])
        self.length_yy = float(design_dictionary[KEY_UNSUPPORTED_LEN_YY])
        
        # End conditions
        self.end_1_z = design_dictionary[KEY_END1]
        self.end_2_z = design_dictionary[KEY_END2]
        self.end_1_y = design_dictionary[KEY_END1_Y]
        self.end_2_y = design_dictionary[KEY_END2_Y]
        
        # Factored loads
        try:
            axial_force = float(design_dictionary[KEY_AXIAL])
        except (ValueError, KeyError):
            axial_force = 0
            
        self.load = Load(
            axial_force=design_dictionary[KEY_AXIAL],
            shear_force=0,
            moment=0,
            moment_minor=0,
            unit_kNm=True
        )
        
        # Design preferences
        self.allowable_utilization_ratio = float(design_dictionary[KEY_ALLOW_UR])
        self.effective_area_factor = float(design_dictionary[KEY_EFFECTIVE_AREA_PARA])
        
        try:
            self.optimization_parameter = design_dictionary[KEY_OPTIMIZATION_PARA]
        except:
            self.optimization_parameter = DEFAULT_VALUES['optimization_parameter']
        
        try:
            self.steel_cost_per_kg = float(design_dictionary[KEY_STEEL_COST])
        except:
            self.steel_cost_per_kg = DEFAULT_VALUES['steel_cost_per_kg']
        
        self.allowed_sections = SECTION_CLASSES
    
    def _validate_design_preferences(self):
        """Validate design preference inputs."""
        # Check utilization ratio
        if not (0.10 < self.allowable_utilization_ratio <= 1.0):
            logger.warning(
                "The defined value of Utilization Ratio in the design preferences tab "
                "is out of the suggested range."
            )
            logger.info("Assuming a default value of 1.0.")
            self.allowable_utilization_ratio = 1.0
        
        # Check effective area factor
        if not (0.10 < self.effective_area_factor <= 1.0):
            logger.warning(
                "The defined value of Effective Area Factor in the design preferences tab "
                "is out of the suggested range."
            )
            logger.info("Assuming a default value of 1.0.")
            self.effective_area_factor = 1.0
    
    def section_classification(self) -> bool:
        """
        Classify sections and check slenderness limits.
        
        Returns:
            True if at least one valid section exists, False otherwise
        """
        self.input_section_list = []
        self.input_section_classification = {}
        self.epsilon = math.sqrt(EPSILON_FACTOR / self.material_property.fy)
        
        for section in self.sec_list:
            trial_section = section.strip("'")
            
            # Get section properties
            section_property = SectionProperties.get_section_property(
                self.sec_profile, trial_section, self.material
            )
            
            # Update material property based on thickness
            self.material_property.connect_to_database_to_get_fy_fu(
                self.material,
                max(section_property.flange_thickness, section_property.web_thickness)
            )
            
            # Classify section
            classifier = SectionClassifier(self.material_property)
            classification = classifier.classify_section(self.sec_profile, section_property)
            
            flange_class = classification['flange_class']
            web_class = classification['web_class']
            section_class = classifier.determine_overall_class(flange_class, web_class)
            
            # Calculate effective lengths
            effective_length_zz = IS800_2007.cl_7_2_2_effective_length_of_prismatic_compression_members(
                self.length_zz, end_1=self.end_1_z, end_2=self.end_2_z
            )
            effective_length_yy = IS800_2007.cl_7_2_2_effective_length_of_prismatic_compression_members(
                self.length_yy, end_1=self.end_1_y, end_2=self.end_2_y
            )
            
            # Check slenderness ratio
            effective_sr_zz = effective_length_zz / section_property.rad_of_gy_z
            effective_sr_yy = effective_length_yy / section_property.rad_of_gy_y
            
            limit = IS800_2007.cl_3_8_max_slenderness_ratio(1)
            if effective_sr_zz > limit and effective_sr_yy > limit:
                logger.warning(
                    "Length provided is beyond the limit allowed. "
                    "[Reference: Cl 3.8, IS 800:2007]"
                )
                continue
            
            # Store classification if section is allowed
            if section_class in self.allowed_sections:
                self.input_section_list.append(trial_section)
                self.input_section_classification[trial_section] = [
                    section_class,
                    flange_class,
                    web_class,
                    classification['flange_ratio'],
                    classification['web_ratio']
                ]
        
        return len(self.input_section_list) > 0
    
    def design_column(self):
        """Perform column design for all valid sections."""
        if not self.flag:
            return
        
        for section in self.input_section_list:
            # Get section properties
            section_property = SectionProperties.get_section_property(
                self.sec_profile, section, self.material
            )
            
            # Update material property
            self.material_property.connect_to_database_to_get_fy_fu(
                self.material,
                max(section_property.flange_thickness, section_property.web_thickness)
            )
            self.epsilon = math.sqrt(EPSILON_FACTOR / self.material_property.fy)
            
            # Calculate design parameters
            result_dict = self._calculate_section_design(section, section_property)
            
            # Store results
            ur = result_dict['ur']
            cost = result_dict['cost']
            
            self.optimum_section_ur_results[ur] = result_dict
            self.optimum_section_ur.append(ur)
            
            self.optimum_section_cost_results[cost] = result_dict
            self.optimum_section_cost.append(cost)
    
    def _calculate_section_design(
        self,
        section: str,
        section_property
    ) -> Dict[str, Any]:
        """
        Calculate all design parameters for a section.
        
        Args:
            section: Section designation
            section_property: Section properties object
            
        Returns:
            Dictionary with all design results
        """
        result = {'Designation': section}
        
        # Section classification
        section_class = self.input_section_classification[section][0]
        result['Section class'] = section_class
        
        # Effective area
        effective_area = EffectiveAreaCalculator.calculate(
            section_class,
            self.sec_profile,
            section_property,
            self.epsilon,
            self.effective_area_factor
        )
        result['Effective area'] = effective_area
        
        # Buckling parameters for both axes
        for axis, suffix in [('z', 'zz'), ('y', 'yy')]:
            axis_results = self._calculate_axis_design(
                section_property,
                axis,
                suffix
            )
            result.update(axis_results)
        
        # Overall design parameters
        result['FCD_2'] = self.material_property.fy / self.gamma_m0
        result['FCD'] = min(result['FCD_zz'], result['FCD_yy'])
        result['Capacity'] = result['FCD'] * effective_area
        result['UR'] = round(self.load.axial_force / result['Capacity'], 3)
        result['Cost'] = self._calculate_section_cost(section_property)
        
        return result
    
    def _calculate_axis_design(
        self,
        section_property,
        axis: str,
        suffix: str
    ) -> Dict[str, Any]:
        """Calculate design parameters for one axis."""
        result = {}
        
        # Effective length
        if axis == 'z':
            effective_length = IS800_2007.cl_7_2_2_effective_length_of_prismatic_compression_members(
                self.length_zz, end_1=self.end_1_z, end_2=self.end_2_z
            )
        else:
            effective_length = IS800_2007.cl_7_2_2_effective_length_of_prismatic_compression_members(
                self.length_yy, end_1=self.end_1_y, end_2=self.end_2_y
            )
        
        result[f'Effective_length_{suffix}'] = effective_length
        
        # Buckling class and imperfection factor
        buckling_class = self._get_buckling_class(section_property, axis)
        imperfection_factor = IS800_2007.cl_7_1_2_1_imperfection_factor(
            buckling_class=buckling_class
        )
        
        result[f'Buckling_curve_{suffix}'] = buckling_class
        result[f'IF_{suffix}'] = imperfection_factor
        
        # Buckling calculations
        calculator = BucklingCalculator(self.material_property, self.gamma_m0)
        buckling_params = calculator.calculate_buckling_parameters(
            section_property, effective_length, axis
        )
        
        result[f'Effective_SR_{suffix}'] = buckling_params['effective_sr']
        result[f'EBS_{suffix}'] = buckling_params['euler_bs']
        result[f'ND_ESR_{suffix}'] = buckling_params['non_dim_eff_sr']
        
        # Design compressive stress
        stress_params = calculator.calculate_design_compressive_stress(
            imperfection_factor,
            buckling_params['non_dim_eff_sr']
        )
        
        result[f'phi_{suffix}'] = stress_params['phi']
        result[f'SRF_{suffix}'] = stress_params['srf']
        result[f'FCD_1_{suffix}'] = stress_params['fcd_1']
        result[f'FCD_{suffix}'] = stress_params['fcd']
        
        return result
    
    def _get_buckling_class(self, section_property, axis: str) -> str:
        """Get buckling class for given axis."""
        if self.sec_profile == VALUES_SEC_PROFILE[0]:  # Beams and Columns
            axis_key = 'z-z' if axis == 'z' else 'y-y'
            
            if section_property.type == 'Rolled':
                return IS800_2007.cl_7_1_2_2_buckling_class_of_crosssections(
                    section_property.flange_width,
                    section_property.depth,
                    section_property.flange_thickness,
                    cross_section='Rolled I-sections',
                    section_type='Hot rolled'
                )[axis_key]
            else:
                return IS800_2007.cl_7_1_2_2_buckling_class_of_crosssections(
                    section_property.flange_width,
                    section_property.depth,
                    section_property.flange_thickness,
                    cross_section='Welded I-section',
                    section_type='Hot rolled'
                )[axis_key]
        else:
            return 'a'
    
    def _calculate_section_cost(self, section_property) -> float:
        """Calculate cost of section in INR."""
        return (
            section_property.unit_mass * 
            section_property.area * 1e-4 * 
            min(self.length_zz, self.length_yy) * 
            self.steel_cost_per_kg
        )
    
    # ========================================================================
    # RESULTS PROCESSING
    # ========================================================================
    
    def results(self):
        """Process and store final design results."""
        # Find failed designs
        failed_designs = [ur for ur in self.optimum_section_ur if ur > 1.0]
        
        if failed_designs:
            temp = min(failed_designs) if len(failed_designs) > 1 else failed_designs[0]
            self.failed_design_dict = self.optimum_section_ur_results.get(temp, {})
        else:
            self.failed_design_dict = {}
        
        # Filter based on optimization parameter
        if self.optimization_parameter == 'Utilization Ratio':
            self._process_ur_results()
        else:
            self._process_cost_results()
        
        # Update overall design status
        self._update_design_status()
    
    def _process_ur_results(self):
        """Process results based on utilization ratio."""
        # Filter sections meeting UR criteria
        valid_sections = [
            ur for ur in self.optimum_section_ur 
            if ur <= min(self.allowable_utilization_ratio, 1.0)
        ]
        
        if not valid_sections:
            logger.warning(
                "The sections selected by the solver from the defined list of sections "
                "did not satisfy the Utilization Ratio (UR) criteria"
            )
            logger.error("The solver did not find any adequate section from the defined list.")
            logger.info("Re-define the list of sections or check the Design Preferences option and re-design.")
            
            self.design_status = False
            
            if self.failed_design_dict:
                logger.info("The details for the best section provided is being shown")
                self.result_UR = self.failed_design_dict['UR']
                self.common_result(
                    self,
                    list_result=self.failed_design_dict,
                    result_type=None
                )
                logger.warning(
                    "Re-define the list of sections or check the Design Preferences option and re-design."
                )
            return
        
        # Select optimum section
        self.failed_design_dict = None
        valid_sections.sort()
        self.result_UR = valid_sections[-1]
        self.design_status = True
        self.common_result(
            self,
            list_result=self.optimum_section_ur_results,
            result_type=self.result_UR
        )
    
    def _process_cost_results(self):
        """Process results based on cost optimization."""
        self.optimum_section_cost.sort()
        self.result_cost = self.optimum_section_cost[0]
        self.design_status = True
    
    def _update_design_status(self):
        """Update overall design status."""
        for status in self.design_status_list:
            if status is False:
                self.design_status = False
                break
        else:
            self.design_status = True
        
        if self.design_status:
            logger.info(": ========== Design Status ============")
            logger.info(": Overall Column design is SAFE")
            logger.info(": ========== End Of Design ============")
        else:
            logger.info(": ========== Design Status ============")
            logger.info(": Overall Column design is UNSAFE")
            logger.info(": ========== End Of Design ============")
    
    def common_result(self, list_result: Dict, result_type: Optional[float]):
        """Extract and store common results from design dictionary."""
        if result_type is None:
            return
        
        results = list_result[result_type]
        
        # Store all result attributes
        self.result_designation = results['Designation']
        self.section_class = self.input_section_classification[self.result_designation][0]
        
        # Log section information
        self._log_section_info()
        
        # Extract results
        self.result_section_class = results['Section class']
        self.result_effective_area = results['Effective area']
        
        # Z-Z axis results
        self.result_bc_zz = results['Buckling_curve_zz']
        self.result_IF_zz = results['IF_zz']
        self.result_eff_len_zz = results['Effective_length_zz']
        self.result_eff_sr_zz = results['Effective_SR_zz']
        self.result_ebs_zz = results['EBS_zz']
        self.result_nd_esr_zz = results['ND_ESR_zz']
        self.result_phi_zz = results['phi_zz']
        self.result_srf_zz = results['SRF_zz']
        self.result_fcd_1_zz = results['FCD_1_zz']
        self.result_fcd_zz = results['FCD_zz']
        
        # Y-Y axis results
        self.result_bc_yy = results['Buckling_curve_yy']
        self.result_IF_yy = results['IF_yy']
        self.result_eff_len_yy = results['Effective_length_yy']
        self.result_eff_sr_yy = results['Effective_SR_yy']
        self.result_ebs_yy = results['EBS_yy']
        self.result_nd_esr_yy = results['ND_ESR_yy']
        self.result_phi_yy = results['phi_yy']
        self.result_srf_yy = results['SRF_yy']
        self.result_fcd_1_yy = results['FCD_1_yy']
        self.result_fcd_yy = results['FCD_yy']
        
        # Overall results
        self.f_cd_2 = results['FCD_2']
        self.result_fcd = results['FCD']
        self.result_capacity = results['Capacity']
        self.result_cost = results['Cost']
    
    def _log_section_info(self):
        """Log section classification and effective area information."""
        if self.section_class == 'Slender':
            logger.warning(
                f"The trial section ({self.result_designation}) is Slender. "
                f"Computing the Effective Sectional Area as per Sec. 9.7.2, "
                f"Fig. 2 (B & C) of The National Building Code of India (NBC), 2016."
            )
        
        if self.effective_area_factor < 1.0:
            actual_area = round(self.result_effective_area / self.effective_area_factor, 2)
            logger.warning("Reducing the effective sectional area as per the definition in the Design Preferences tab.")
            logger.info(
                f"The actual effective area is {actual_area} mm2 and the reduced effective area is "
                f"{self.result_effective_area} mm2 [Reference: Cl. 7.3.2, IS 800:2007]"
            )
        else:
            if self.section_class != 'Slender':
                logger.info(
                    "The effective sectional area is taken as 100% of the cross-sectional area "
                    "[Reference: Cl. 7.3.2, IS 800:2007]."
                )
        
        classification = self.input_section_classification[self.result_designation]
        logger.info(
            f"The section is {classification[0]}. The {self.result_designation} section has "
            f"{classification[1]} flange({round(classification[3], 2)}) and "
            f"{classification[2]} web({round(classification[4], 2)}). "
            f"[Reference: Cl 3.7, IS 800:2007]."
        )
    
    # ========================================================================
    # REPORT GENERATION
    # ========================================================================
    
    def save_design(self, popup_summary: Dict):
        """Generate and save design report."""
        if (self.design_status and self.failed_design_dict is None) or \
           (not self.design_status and len(self.failed_design_dict) > 0):
            
            # Get section property for report
            section_property = SectionProperties.get_section_property(
                self.sec_profile,
                self.result_designation,
                self.material
            )
            
            # Generate report data
            self._generate_report_column_data(section_property)
            self._generate_report_input_data()
            self._generate_report_checks(section_property)
        else:
            # Failed design report
            self._generate_failed_report()
        
        # Generate LaTeX report
        self._save_latex_report(popup_summary)
    
    def _generate_report_column_data(self, section_property):
        """Generate column data for report."""
        if self.sec_profile in ['Columns', 'Beams', VALUES_SEC_PROFILE[0]]:
            self.report_column = {
                KEY_DISP_SEC_PROFILE: "ISection",
                KEY_DISP_SECSIZE: (section_property.designation, self.sec_profile),
                KEY_DISP_COLSEC_REPORT: section_property.designation,
                KEY_DISP_MATERIAL: section_property.material,
                KEY_REPORT_MASS: section_property.mass,
                KEY_REPORT_AREA: round(section_property.area * 1e-2, 2),
                KEY_REPORT_DEPTH: section_property.depth,
                KEY_REPORT_WIDTH: section_property.flange_width,
                KEY_REPORT_WEB_THK: section_property.web_thickness,
                KEY_REPORT_FLANGE_THK: section_property.flange_thickness,
                KEY_DISP_FLANGE_S_REPORT: section_property.flange_slope,
                KEY_REPORT_R1: section_property.root_radius,
                KEY_REPORT_R2: section_property.toe_radius,
                KEY_REPORT_IZ: round(section_property.mom_inertia_z * 1e-4, 2),
                KEY_REPORT_IY: round(section_property.mom_inertia_y * 1e-4, 2),
                KEY_REPORT_RZ: round(section_property.rad_of_gy_z * 1e-1, 2),
                KEY_REPORT_RY: round(section_property.rad_of_gy_y * 1e-1, 2),
                KEY_REPORT_ZEZ: round(section_property.elast_sec_mod_z * 1e-3, 2),
                KEY_REPORT_ZEY: round(section_property.elast_sec_mod_y * 1e-3, 2),
                KEY_REPORT_ZPZ: round(section_property.plast_sec_mod_z * 1e-3, 2),
                KEY_REPORT_ZPY: round(section_property.plast_sec_mod_y * 1e-3, 2)
            }
        else:
            self.report_column = {
                KEY_DISP_COLSEC_REPORT: section_property.designation,
                KEY_DISP_MATERIAL: section_property.material,
                KEY_REPORT_MASS: section_property.mass,
                KEY_REPORT_AREA: round(section_property.area * 1e-2, 2),
                KEY_REPORT_DEPTH: section_property.depth,
                KEY_REPORT_WIDTH: section_property.flange_width,
                KEY_REPORT_WEB_THK: section_property.web_thickness,
                KEY_REPORT_FLANGE_THK: section_property.flange_thickness,
                KEY_DISP_FLANGE_S_REPORT: section_property.flange_slope
            }
    
    def _generate_report_input_data(self):
        """Generate input data for report."""
        self.report_input = {
            KEY_MODULE: self.module,
            KEY_DISP_AXIAL: self.load.axial_force * 1e-3,
            KEY_DISP_ACTUAL_LEN_ZZ: self.length_zz,
            KEY_DISP_ACTUAL_LEN_YY: self.length_yy,
            KEY_DISP_SEC_PROFILE: self.sec_profile,
            KEY_DISP_SECSIZE: self.result_section_class,
            KEY_DISP_END1: self.end_1_z,
            KEY_DISP_END2: self.end_2_z,
            KEY_DISP_END1_Y: self.end_1_y,
            KEY_DISP_END2_Y: self.end_2_y,
            "Column Section - Mechanical Properties": "TITLE",
            KEY_MATERIAL: self.material,
            KEY_DISP_ULTIMATE_STRENGTH_REPORT: self.material_property.fu,
            KEY_DISP_YIELD_STRENGTH_REPORT: self.material_property.fy,
            KEY_DISP_EFFECTIVE_AREA_PARA: self.effective_area_factor,
            KEY_DISP_SECSIZE: str(self.sec_list),
            "Selected Section Details": self.report_column,
        }
    
    def _generate_report_checks(self, section_property):
        """Generate design checks for report."""
        self.report_check = []
        
        # Selected member data
        self.report_check.append((
            'Selected', 'Selected Member Data',
            '|p{5cm}|p{2cm}|p{2cm}|p{2cm}|p{4cm}|'
        ))
        
        h = (section_property.depth - 2 * (
            section_property.flange_thickness + section_property.root_radius
        ))
        h_bf_ratio = h / section_property.flange_width
        
        # Buckling class compatibility check
        self.report_check.append((
            'SubSection', 'Buckling Class - Compatibility Check',
            '|p{4cm}|p{3.5cm}|p{6.5cm}|p{2cm}|'
        ))
        
        self.report_check.append((
            "h/bf and tf for YY Axis",
            comp_column_class_section_check_required(
                h, section_property.flange_width, section_property.flange_thickness, "YY"
            ),
            comp_column_class_section_check_provided(
                h, section_property.flange_width, section_property.flange_thickness,
                round(h_bf_ratio, 2), "YY"
            ),
            'Compatible'
        ))
        
        self.report_check.append((
            "h/bf and tf for ZZ Axis",
            comp_column_class_section_check_required(
                h, section_property.flange_width, section_property.flange_thickness, "ZZ"
            ),
            comp_column_class_section_check_provided(
                h, section_property.flange_width, section_property.flange_thickness,
                round(h_bf_ratio, 2), "ZZ"
            ),
            'Compatible'
        ))
        
        # Section classification
        self.report_check.append((
            'SubSection', 'Section Classification',
            '|p{3cm}|p{3.5cm}|p{8.5cm}|p{1cm}|'
        ))
        
        classification = self.input_section_classification[self.result_designation]
        
        self.report_check.append((
            'Web Class', 'Axial Compression',
            cl_3_7_2_section_classification_web(
                round(h, 2), round(section_property.web_thickness, 2),
                round(classification[4], 2), self.epsilon, section_property.type,
                classification[2]
            ),
            ' '
        ))
        
        self.report_check.append((
            'Flange Class', section_property.type,
            cl_3_7_2_section_classification_flange(
                round(section_property.flange_width / 2, 2),
                round(section_property.flange_thickness, 2),
                round(classification[3], 2), self.epsilon, classification[1]
            ),
            ' '
        ))
        
        self.report_check.append((
            'Section Class', ' ',
            cl_3_7_2_section_classification(classification[0]),
            ' '
        ))
        
        # Imperfection factor table
        self.report_check.append((
            'NewTable', 'Imperfection Factor',
            '|p{3cm}|p{5cm}|p{5cm}|p{3cm}|'
        ))
        
        self.report_check.append((
            'YY', self.result_bc_yy.upper(), self.result_IF_yy, ''
        ))
        
        self.report_check.append((
            'ZZ', self.result_bc_zz.upper(), self.result_IF_zz, ''
        ))
        
        # Slenderness ratio calculations
        K_yy = self.result_eff_len_yy / self.length_yy
        K_zz = self.result_eff_len_zz / self.length_zz
        
        self.report_check.append((
            'SubSection', 'Slenderness Ratio',
            '|p{4cm}|p{2cm}|p{7cm}|p{3cm}|'
        ))
        
        self.report_check.append((
            "Effective Slenderness Ratio (For YY Axis)", ' ',
            cl_7_1_2_effective_slenderness_ratio(
                K_yy, self.length_yy, section_property.rad_of_gy_y,
                round(self.result_eff_sr_yy, 2)
            ),
            ' '
        ))
        
        self.report_check.append((
            "Effective Slenderness Ratio (For ZZ Axis)", ' ',
            cl_7_1_2_effective_slenderness_ratio(
                K_zz, self.length_zz, section_property.rad_of_gy_z,
                round(self.result_eff_sr_zz, 2)
            ),
            ' '
        ))
        
        # Design checks
        self.report_check.append((
            'SubSection', 'Checks',
            '|p{4cm}|p{2cm}|p{7cm}|p{3cm}|'
        ))
        
        self.report_check.append((
            r'$\phi_{yy}, ' ',
            cl_8_7_1_5_phi(
                self.result_IF_yy, round(self.result_nd_esr_yy, 2),
                round(self.result_phi_yy, 2)
            ),
            ' '
        ))
        
        self.report_check.append((
            r'$\phi_{zz}, ' ',
            cl_8_7_1_5_phi(
                self.result_IF_zz, round(self.result_nd_esr_zz, 2),
                round(self.result_phi_zz, 2)
            ),
            ' '
        ))
        
        self.report_check.append((
            r'$F_{cd,yy} \, \left( \frac{N}{\text{mm}^2} \right), ' ',
            cl_8_7_1_5_Buckling(
                self.material_property.fy, self.gamma_m0,
                round(self.result_nd_esr_yy, 2), round(self.result_phi_yy, 2),
                round(self.f_cd_2, 2), round(self.result_fcd_yy, 2)
            ),
            ' '
        ))
        
        self.report_check.append((
            r'$F_{cd,zz} \, \left( \frac{N}{\text{mm}^2} \right), ' ',
            cl_8_7_1_5_Buckling(
                self.material_property.fy, self.gamma_m0,
                round(self.result_nd_esr_zz, 2), round(self.result_phi_zz, 2),
                round(self.f_cd_2, 2), round(self.result_fcd_zz, 2)
            ),
            ' '
        ))
        
        self.report_check.append((
            r'Design Compressive Strength (\( P_d \)) (For the most critical value of \( F_{cd} \))',
            self.load.axial_force * 1e-3,
            cl_7_1_2_design_compressive_strength(
                round(self.result_capacity / 1000, 2), section_property.area,
                round(self.result_fcd, 2), self.load.axial_force * 1e-3
            ),
            get_pass_fail(
                self.load.axial_force * 1e-3, round(self.result_capacity, 2),
                relation="leq"
            )
        ))
    
    def _generate_failed_report(self):
        """Generate report data for failed design."""
        self.report_input = {
            KEY_MODULE: self.module,
            KEY_DISP_AXIAL: self.load.axial_force * 1e-3,
            KEY_DISP_ACTUAL_LEN_ZZ: self.length_zz,
            KEY_DISP_ACTUAL_LEN_YY: self.length_yy,
            KEY_DISP_SEC_PROFILE: self.sec_profile,
            KEY_DISP_SECSIZE: str(self.sec_list),
            KEY_DISP_END1: self.end_1_z,
            KEY_DISP_END2: self.end_2_z,
            KEY_DISP_END1_Y: self.end_1_y,
            KEY_DISP_END2_Y: self.end_2_y,
            "Column Section - Mechanical Properties": "TITLE",
            KEY_MATERIAL: self.material,
            KEY_DISP_ULTIMATE_STRENGTH_REPORT: self.material_property.fu,
            KEY_DISP_YIELD_STRENGTH_REPORT: self.material_property.fy,
            KEY_DISP_EFFECTIVE_AREA_PARA: self.effective_area_factor,
        }
        
        self.report_check = [(
            'Selected', 'All Members Failed',
            '|p{5cm}|p{2cm}|p{2cm}|p{2cm}|p{4cm}|'
        )]
    
    def _save_latex_report(self, popup_summary: Dict):
        """Save LaTeX report to file."""
        Disp_2d_image = []
        Disp_3D_image = ""
        
        rel_path = os.path.abspath(".")
        rel_path = rel_path.replace("\\", "/")
        fname_no_ext = popup_summary['filename']
        
        CreateLatex.save_latex(
            CreateLatex(),
            self.report_input,
            self.report_check,
            popup_summary,
            fname_no_ext,
            rel_path,
            Disp_2d_image,
            Disp_3D_image,
            module=self.module
        )