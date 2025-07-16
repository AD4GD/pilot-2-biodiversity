import unittest
from unittest import TestCase
from enrichment.lulc_data_processor import LULCDataPreprocessor
import sys
import io
from contextlib import redirect_stdout
# from unittest.mock import Mock, patch

# local imports required for the tests
import yaml
#from utils import load_yaml,extract_attribute_values,get_lulc_template,read_years_from_config
from raster_metadata import RasterMetadata
import os
from osgeo import ogr

class TestLulcDataProcessor(TestCase):
    @classmethod
    def setUpClass(cls):
        """Setup the test environment once before all tests"""
        #warnings.simplefilter("ignore", ResourceWarning)

        config_path = "./config/config.yaml"
        # cls.assertTrue(os.path.exists(config_path))
        with open(config_path , 'r') as file:
            cls.config = yaml.safe_load(file)
        cls.working_dir = os.getcwd()
        cls.vector_dir = os.path.join(cls.working_dir,cls.config["case_study_dir"],cls.config['vector_dir'])
        cls.year = 2017
        cls.lulc_filepath = './data/shared/input/lulc/lulc_albera_ext_concat_{year}.tif'.format(year=cls.year)
        cls.ldp = LULCDataPreprocessor(
            cls.config, 
            cls.lulc_filepath, 
            cls.working_dir
        )


    def test_lulc_mapping(self):
        expected = {'lulc_road': 4, 'lulc_railway': 4, 'lulc_water': 2, 'lulc_vineyard': 22}
        self.assertEqual(
            self.ldp.lulc_mapping(self.ldp.impedance_file)
            , expected
        )