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
from testing.testing_toolkit import check_vector_pixels, check_raster_metadata, calculate_raster_difference


class TestImpedanceWrapperProcessor(TestCase):
    """
    Test suite for the Impedance wrapper class.
    """

    @classmethod
    def setUpClass(cls):
        """Setup the test environment once before all tests"""
        config_path = "./config/config_testing.yaml"
        with open(config_path, 'r') as file:
            cls.config = yaml.safe_load(file)

        cls.working_dir = os.path.join(os.getcwd(), 'testing')

        cls.impedance_wrapper = ImpedanceWrapper(working_dir=cls.working_dir,
                                                 config_path=config_path,
                                                 verbose=True)


    def test_process_impedance_config(self):
        """
        Test the process_impedance_config method.
        1. test if stressors were made for LULC
        2. test the congfig file is valid
        3. test if impedance_stressors dict variable has all the expected keys
        """

        pass

    def test_reclassify_lulc2impedance(self):
        """
        Test the reclassify_lulc2impedance method.
        1. test if the reclassified raster is created
        2. test if the reclassified raster has the expected metadata
        3. test at least one specific pixel value in the reclassified raster
        """
        pass


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
      