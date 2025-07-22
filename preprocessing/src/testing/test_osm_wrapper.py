import unittest
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch
from osm.osm_wrapper import OSMWrapper
import requests

# local imports required for the tests
from osgeo import gdal
import numpy as np
import pandas as pd
import yaml
import os
import json
from testing.testing_toolkit import check_vector_pixels, check_raster_metadata, calculate_raster_difference

#TODO fix mock data intercept. it is using the same data for all intercepts
class TestOsmWrapperProcessor(TestCase):
    """
    Test suite for the OSMWrapper class.
    """

    @classmethod
    def setUpClass(cls):
        """Setup the test environment once before all tests"""
        config_path = "./config/config_testing.yaml"
        with open(config_path, 'r') as file:
            cls.config = yaml.safe_load(file)

        cls.working_dir = os.path.join(os.getcwd(), 'testing')

        cls.osm_wrapper_overpass = OSMWrapper(working_dir=cls.working_dir,
                                     config_path=config_path,
                                     use_lulc_pa=False,
                                     api_type="overpass",
                                     verbose=True)
        
        cls.osm_wrapper_ohsome = OSMWrapper(working_dir=cls.working_dir,
                                        config_path=config_path,
                                        use_lulc_pa=False,
                                        api_type="ohsome",
                                        verbose=True)
    
    def check_osm_to_geojson(self, years:list, geojson_path:str, gpkg_path:str):
        """
        Test the osm_overpass_to_geojson method.
        1. test that the geojson files were created
        2. test that the geojson files contain features
        """
        # Check if the geojson files were created
        for file in os.listdir(geojson_path):
            if file.endswith('filtered.geojson'):
                with open(os.path.join(geojson_path, file), 'r') as f:
                    geojson_content = json.load(f)
                    # Check the feature count is greater than 0
                    self.assertGreater(len(geojson_content.get('features', [])), 0, f"The geojson file {file} is empty.")

    def check_osm_to_gpkg(self,api_type:str):
        """
        Test the osm_overpass_to_gpkg method.
        1. test that the output files are created
        2. test that the output files contain all the expected layers
        3. test that each layer has a feature count greater than 0
        """
        if api_type == "ohsome":
            osm_wrapper = self.osm_wrapper_ohsome
        elif api_type == "overpass":
            osm_wrapper = self.osm_wrapper_overpass
        years = [2012, 2017, 2022]
        # get layer names from the config file
        layer_names = {key[9:] for key in self.config.keys() if key.startswith("overpass_")}
        
        output_files = osm_wrapper.osm_to_merged_gpkg(years, api_type=api_type)

        # Check if the output files are created
        for file in output_files:
            self.assertTrue(os.path.exists(file), f"Output file {file} does not exist.")

            # open each gpkg file and check if it has all the correct layers (i.e. the layers from the config file)
            ds = gdal.OpenEx(file, gdal.OF_VECTOR)
            self.assertIsNotNone(ds, f"Failed to open the GeoPackage file {file}.")
            layer_names_in_file = {ds.GetLayerByIndex(i).GetName() for i in range(ds.GetLayerCount())}
            self.assertTrue(layer_names.issubset(layer_names_in_file), f"GeoPackage file {file} does not contain all expected layers: {layer_names}. Found layers: {layer_names_in_file}.")
            
            # test that each layer has a feature count greater than 0
            for i in range(ds.GetLayerCount()):
                layer = ds.GetLayerByIndex(i)
                feature_count = layer.GetFeatureCount()
                self.assertGreater(feature_count, 0, f"The layer {layer.GetName()} in the GeoPackage file {file} is empty.")
            ds = None  # Close the dataset

        
        # check intermediate geopackage files exist for all years and layers have a feature count greater than 0
        gpkg_files = [f for f in os.listdir(osm_wrapper.gpkg_dir) if f.endswith('.gpkg')]
        self.assertTrue(len(gpkg_files) > 0, "No GeoPackage files were created.")
        # each year should have 5 gpkg files (one for each osm tag)
        years_dict = {year: 0 for year in years}
        for gpkg_file in gpkg_files:
            # skip over merged ones in case it is left in there from previous runs
            if 'merged' in gpkg_file:
                continue
            # check each year's gpkg file
            year = int(gpkg_file.split('_')[-1].split('.')[0])
            self.assertIn(year, years, f"Unexpected year {year} found in GeoPackage file {gpkg_file}.")
            years_dict[year] += 1

            ds = gdal.OpenEx(os.path.join(osm_wrapper.gpkg_dir, gpkg_file), gdal.OF_VECTOR)
            self.assertIsNotNone(ds, f"Failed to open the GeoPackage file {gpkg_file}.")
            for i in range(ds.GetLayerCount()):
                layer = ds.GetLayerByIndex(i)
                feature_count = layer.GetFeatureCount()
                self.assertGreater(feature_count, 0, f"The layer {layer.GetName()} in the GeoPackage file {gpkg_file} is empty.")
            ds = None

        # check that each year has 5 layers
        # for year, count in years_dict.items():
        #     self.assertEqual(count, 5, f"Year {year} does not have 5 GeoPackage files. Found {count} files.")

    def osm_cleanup(self, osm_wrapper: OSMWrapper):
        """
        Test the osm_cleanup method for both Overpass and Ohsome APIs.
        1. test that the osm data directory has no geojson files
        2. test that the gpkg files only have the merged files
        """
        # we can use either instance of OSMWrapper since the method is the same for both Overpass and Ohsome
        osm_wrapper.delete_temp_files(delete_geojsons=True, delete_gpkg_files=True)

        # check that the osm data directory has no geojson files
        geojson_files = [f for f in os.listdir(osm_wrapper.osm_output_data_dir) if f.endswith('.geojson')]
        self.assertTrue(len(geojson_files) == 0, "Temporary GeoJSON files were not deleted.")

        # check that gpkg files only have the merged files
        gpkg_files = [f for f in os.listdir(osm_wrapper.gpkg_dir) if f.endswith('.gpkg')]
        self.assertTrue(len(gpkg_files) == 3, "Temporary GeoPackage files were not deleted.")

    
    def test_1_osm_overpass_to_geojson(self):
        """
        Test the osm_overpass_to_geojson method.
        """
        years = [2012, 2017, 2022]
        skip_fetch = False

        #get files 
        path = os.path.join(self.osm_wrapper_overpass.osm_output_data_dir)

        files = []
        for file in os.listdir(path):
            # # only consider the latest files because all previous files are derived from the latest ones
            if file.endswith('.json') and 'overpass_pre' in file:
                files.append(file)
        # get the file order from the config file
        file_order = [key.split('_')[-1] for key in self.config.keys() if 'overpass_' in key]
        # sort files by the order in the config file (type then year)
        files.sort(key=lambda x: (int(x.split('_')[-1].split('.')[0]), file_order.index(x.split('_')[0])))
    

        # Mock the requests.session.post method to return predefined responses
        side_effects = []
        for file in files:
            print(f"Processing file: {file}")
            file_path = os.path.join(path, file)
            file_content = {}
            with open(file_path, 'r') as f:
                file_content = json.load(f)
                side_effects.append(Mock(status_code=200, json=lambda file_content_output = file_content: file_content_output))


        with patch('requests.get') as mock_get:
            mock_get.side_effect = side_effects
            self.osm_wrapper_overpass.osm_overpass_to_geojson(years, skip_fetch)

            # Check that the mock methods were called the expected number of times
            # 5 for each osm tag * 3 years = 15
            self.assertEqual(mock_get.call_count, 15)

        self.check_osm_to_geojson(years, geojson_path=path, gpkg_path=self.osm_wrapper_overpass.gpkg_dir)

    def test_2_osm_overpass_to_gpkg(self):
        """
        Test the osm_overpass_to_gpkg method for Overpass API.
        """
        self.check_osm_to_gpkg(api_type="overpass")

    def test_3_osm_overpass_cleanup(self):
        """
        Test the osm_cleanup method for Overpass API.
        """
        self.osm_cleanup(self.osm_wrapper_overpass)

    def test_4_osm_ohsome_to_geojson(self):
        """
        Test the osm_ohsome_to_geojson method.
        1. test files exist
        2. test feature count of the geojson files is greater than 0
        """
        years = [2012, 2017, 2022]
        skip_fetch = False

        path = os.path.join(self.osm_wrapper_overpass.osm_output_data_dir)

        files = []
        for file in os.listdir(path):
            # only consider the latest files because all previous files are derived from the latest ones
            if 'ohsome_pre_2022.json' in file:
                files.append(file)
        # get the file order from the config file
        file_order = [key.split('_')[-1] for key in self.config.keys() if 'ohsome_' in key]
        # sort files by the order in the config file
        files.sort(key=lambda x: file_order.index(x.split('_')[0]))
    
        # Mock the requests.session.post method to return predefined responses
        side_effects = []
        for file in files:
            print(f"Processing file: {file}")
            file_path = os.path.join(path, file)
            file_content = {}
            with open(file_path, 'r') as f:
                file_content = json.load(f)
                side_effects.append(Mock(status_code=200, json=lambda file_content_output = file_content: file_content_output))

        with patch('requests.Session.post') as mock_methods:
            mock_methods.side_effect = side_effects
            self.osm_wrapper_ohsome.osm_ohsome_to_geojson(years, skip_fetch)

            # Check that the mock methods were called the expected number of times (5 times for each osm tag)
            self.assertEqual(mock_methods.call_count, len(file_order), "The post method was not called the expected number of times.")

        # Check if the geojson files were created
        self.check_osm_to_geojson(years,geojson_path=path,gpkg_path=self.osm_wrapper_ohsome.gpkg_dir)

    def test_5_osm_ohsome_to_gpkg(self):
        """
        Test the osm_ohsome_to_gpkg method for Ohsome API.
        """
        self.check_osm_to_gpkg(api_type="ohsome")

    def test_6_osm_cleanup_ohsome(self):
        """
        Test the osm_cleanup method.
        """
        self.osm_cleanup(osm_wrapper=self.osm_wrapper_ohsome)



if __name__ == '__main__':
    unittest.main()
        
        