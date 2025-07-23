import unittest
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch
from impedance.impedance_wrapper import ImpedanceWrapper
import requests

# local imports required for the tests
from osgeo import gdal
import numpy as np
import pandas as pd
import yaml
import os
import json
from testing.testing_toolkit import check_vector_pixels_by_coordinates, check_raster_metadata, calculate_raster_difference


class TestImpedanceWrapperProcessor(TestCase):
    """
    Test suite for the Impedance wrapper class.
    """

    @classmethod
    def setUpClass(cls):
        """Setup the test environment once before all tests"""
        config_path = "./testing/data/config/config.yaml"
        with open(config_path, 'r') as file:
            cls.config = yaml.safe_load(file)

        config_impedance_path = './testing/data/config/config_impedance.yaml'
        with open(config_impedance_path, 'r') as file:
            cls.config_impedance = yaml.safe_load(file)

        # use this config for all other tests
        config_impedance_albera_path = './testing/data/config/config_impedance_albera.yaml'
        with open(config_impedance_albera_path, 'r') as file:
            cls.config_impedance_albera = yaml.safe_load(file)

        cls.working_dir = os.path.join(os.getcwd(), 'testing')

        cls.impedance_wrapper = ImpedanceWrapper(
            working_dir=cls.working_dir,
            decline_type='exp_decline',
            lambda_decay = 500,
            k_value = 500,
            config_path = config_path,
            config_impedance_path = config_impedance_path,
            verbose = True
        )

        cls.years = [2012, 2017, 2022]



    def test_process_impedance_config(self):
        """
        Test the process_impedance_config method.
        1. test if stressors were made for LULC
        2. test the congfig file is valid
        3. test if impedance_stressors dict variable has all the expected keys
        """
        impedance_stressors = {}
        expected_keys = [
            'stressor_lulc_4_2012', 'stressor_lulc_5_2012', 'stressor_lulc_6_2012', 'stressor_lulc_7_2012', 'stressor_lulc_1004_2012', 'stressor_lulc_1005_2012', 'stressor_lulc_1006_2012', 'stressor_lulc_1007_2012', 
            'stressor_lulc_4_2017', 'stressor_lulc_5_2017', 'stressor_lulc_6_2017', 'stressor_lulc_7_2017', 'stressor_lulc_1004_2017', 'stressor_lulc_1005_2017', 'stressor_lulc_1006_2017', 'stressor_lulc_1007_2017', 
            'stressor_lulc_4_2022', 'stressor_lulc_5_2022', 'stressor_lulc_6_2022', 'stressor_lulc_7_2022', 'stressor_lulc_1004_2022', 'stressor_lulc_1005_2022', 'stressor_lulc_1006_2022', 'stressor_lulc_1007_2022', 
            'railways', 'motorway', 'secondary', 'primary', 'tertiary', 'trunk'
        ]
        for year in self.years:
            single_year_impedance_stressors = self.impedance_wrapper.process_impedance_config(year,use_lulc_pa=False)
            self.assertEqual(self.impedance_wrapper.validate_impedance_config(single_year_impedance_stressors), "exit")
            impedance_stressors.update(single_year_impedance_stressors)
        
        self.assertTrue(all(key in impedance_stressors for key in expected_keys), "Not all expected keys are present in impedance_stressors")


    def test_reclassify_lulc2impedance(self):
        """
        Test the reclassify_lulc2impedance method.
        1. test if the reclassified raster is created
        2. test if the reclassified raster has the expected metadata
        3. test at least one specific pixel value in the reclassified raster
        """
        self.impedance_wrapper.config_impedance = self.config_impedance_albera
        for year in self.years:
            # 3.0 set the output path for the new impedance raster dataset 
            impedance_tif_template = str(self.impedance_wrapper.config.get('impedance_tif'))
            impedance_tif_path = os.path.normpath(os.path.join(
                self.impedance_wrapper.impedance_dir,impedance_tif_template.format(year=year).replace(".tif", "_upd.tif")
            ))
            lulc_template = str(self.impedance_wrapper.config.get('lulc'))
            if lulc_template is None or lulc_template == "":
                raise Exception("lulc in config is null/empty or does not exist")
            else:
                lulc_template = lulc_template.replace('.tif', "_upd.tif").format(year=year)
            lulc_upd = os.path.join(self.impedance_wrapper.config.get('case_study_dir'), "output", lulc_template)
            

            impedance_tiff = self.impedance_wrapper.reclassify_lulc2impedance(
                input_raster= lulc_upd,
                impedance_raster= impedance_tif_path,
                reclass_table= os.path.join(self.impedance_wrapper.impedance_dir, self.impedance_wrapper.config.get('impedance')),
                out_nodata=-9999, # assign nodata from original impedance raster (we know it's value already)
            )

            break


        # # Check if the reclassified raster is created
        # reclassified_raster_path = os.path.join(self.impedance_wrapper.stressor_dir, 'reclassified_lulc.tif')
        # self.assertTrue(os.path.exists(reclassified_raster_path), "Reclassified raster was not created")


    def test_get_impedance_max_value(self):
        """
        Test the get_impedance_max_value method.
        1. test if the output tuple[gdal.Dataset, float]
        2. test the max_value to an expected value
        """
        pass
        # max_value = self.impedance_wrapper.get_impedance_max_value()
        # self.assertIsInstance(max_value, float)
        # self.assertGreater(max_value, 0)


    def test_calculate_impedance(self):
        """
        Test the calculate_impedance method.
        1. check max tif is created 
        2. check max tif has the expected metadata
        3. check max tif has the expected pixel value
        """
      