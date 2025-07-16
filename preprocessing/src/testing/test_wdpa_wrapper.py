import unittest
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch
from protected_areas.wpda_wrapper import WDPAWrapper
import requests

# local imports required for the tests
from osgeo import gdal
import numpy as np
import pandas as pd
import yaml
import os
import json
from testing.testing_toolkit import check_vector_pixels, check_raster_metadata, calculate_raster_difference

class TestWdpaWrapperProcessor(TestCase):
    @classmethod
    def setUpClass(cls):
        """Setup the test environment once before all tests"""
        config_path = "./config/config.yaml"
        cls.wwp = WDPAWrapper(
            working_dir=os.getcwd(),
            config_path=config_path,
            verbose=True,
        )

        with open(config_path, 'r') as file:
            cls.config = dict(yaml.safe_load(file))
        cls.working_dir = os.getcwd()
        cls.pa_geojson_dir = os.path.join(cls.working_dir, "data", "shared", "input", "protected_areas")
        cls.pa_output_dir = os.path.join(cls.working_dir, cls.config["case_study_dir"], "output", "protected_areas")
        cls.pa_output_data_dir = os.path.join(cls.pa_output_dir, "data")

        if cls.config["subcase_study"]:
            cls.impedance_dir = os.path.join(cls.working_dir, cls.config["case_study_dir"], cls.config['impedance_dir'].split('/')[0], cls.config["subcase_study"] + "_" + cls.config['impedance_dir'].split('/')[-1])
        else:
            cls.impedance_dir = os.path.join(cls.working_dir, cls.config["case_study_dir"], cls.config['impedance_dir'])

        cls.affinty = os.path.join(cls.working_dir, cls.config["case_study_dir"],"output", "affinity")
        cls.test_outputs = []

    @classmethod
    def tearDownClass(cls):
        """Cleanup the test environment after all tests"""
        # delete files with test_ prefix
        for file in os.listdir(cls.pa_output_dir):
            if os.path.exists(file) and file.startswith("test_"):
                os.remove(os.path.join(cls.pa_output_dir, file))

        # clean up other test outputs
        for file in cls.test_outputs:
            if os.path.exists(file):
                os.remove(file)



    @patch('requests.post')
    def test_get_lulc_country_codes(self, mock_post):
        """Test if the method returns the correct country codes."""
        # Mock the response from ohsome API
        mock_response = Mock()
        mock_response.status_code = 200
        file = os.path.join(self.pa_output_dir, "countries.geojson")
        with open(file, 'r') as f:
            mock_response.json.return_value = json.load(f)

        # Set the mock post method to return the mocked response
        mock_post.return_value = mock_response

        expected_country_codes = {'ESP', 'FRA'}
        country_codes = self.wwp.get_lulc_country_codes()
        mock_post.assert_called_once()

        # assertions on output
        self.assertIsInstance(country_codes, set)
        self.assertGreater(len(country_codes), 0)
        self.assertEqual(country_codes, expected_country_codes)



    def test_protected_area_to_merged_geopackage(self):
        """Test if the method creates a merged GeoPackage file."""
        country_codes = {'FRA', 'ESP'}

        #read in testing/data FRA and ESP then append a new json response with {"protected_areas": []} to simulate no protected areas found
        side_effect = [
            Mock(status_code=200, json=lambda: json.load(open(os.path.join(os.getcwd(), "testing/data", 'FRA_PA.json'), 'r'))),
            Mock(status_code=200, json=lambda: {"protected_areas": []}),  # Simulate no more protected areas found
            Mock(status_code=200, json=lambda: json.load(open(os.path.join(os.getcwd(),"testing/data", 'ESP_PA.json'), 'r'))),
            Mock(status_code=200, json=lambda: {"protected_areas": []}), # Simulate no more protected areas found
        ]

        with patch.multiple('requests', get=Mock(side_effect=side_effect)):
            # Call the method to create a merged GeoPackage
            merged_gpkg = self.wwp.protected_area_to_merged_geopackage(country_codes,output_file="test_merged_pa.gpkg", skip_fetch=False)

            # Check if the merged GeoPackage file exists
            self.assertTrue(os.path.exists(merged_gpkg))

            # cleanup
            self.test_outputs.append(merged_gpkg)


    @patch('protected_areas.wpda_wrapper.WDPAWrapper.protected_area_to_merged_geopackage')
    def test_rasterize_protected_areas(self, mocked_geopackage):
        """Test if the method rasterizes protected areas correctly."""
        country_codes = {'FRA', 'ESP'}
        mocked_geopackage.return_value = os.path.join(self.pa_geojson_dir, "test_merged_pa.gpkg")

        merged_gpkg = self.wwp.protected_area_to_merged_geopackage(country_codes,output_file="test_merged_pa.gpkg", skip_fetch=True)
        # Call the method to rasterize protected areas
        lulc_dir = self.wwp.config.get("lulc_dir")
        lulc_template = self.wwp.config['lulc']
        self.wwp.rasterize_protected_areas(merged_gpkg=merged_gpkg, lulc_dir=lulc_dir, lulc_template=lulc_template.split('_{year}.tif')[0], pa_to_yearly_rasters=False)

        # Check if the rasterized files are created in the output directory
        filepath = os.path.join(self.pa_output_dir, "pa_rasters")
        output_files = os.listdir(filepath)
       
        self.assertTrue(any(file.endswith('.tif') for file in output_files))

        #cleanup
        for file in output_files:
            self.test_outputs.append(os.path.join(filepath, file))  


    def test_sum_lulc_pa_rasters(self):
        """Test if the method sums LULC protected area rasters correctly."""
        # Define input and output paths
        output_path = os.path.join(self.config["lulc_pa_dir"])
        lulc_dir = self.wwp.config.get("lulc_dir")
        lulc_template = str(self.wwp.config['lulc'])
        pa_path = os.path.join(self.pa_output_dir, "pa_rasters")

        # Call the method to sum LULC protected area rasters
        output_files = self.wwp.sum_lulc_pa_rasters(output_path=output_path, lulc_dir=lulc_dir, lulc_template=lulc_template, pa_path=pa_path, use_yearly_pa_rasters=False)

        
        # Check if the summed rasters have different values to original rasters
        for file in output_files:
            self.assertTrue(os.path.exists(file))
           
            # validate metadata of the files
            check_raster_metadata(
                self,
                file,
                expected_nodata=-9999.0,
                expected_cell_size=30,
                expected_is_cartesian=True,
                expected_x_min=486435,
                expected_y_min=4683645,
                expected_x_max=517005,
                expected_y_max=4705995
            )

            # get matching lulc raster file
            year = file.split("_")[-1].split(".")[0]
            matching_lulc_file = os.path.join(lulc_dir, lulc_template.format(year=year))

            # check raster difference
            self.assertTrue(
                calculate_raster_difference(
                    before_raster_path=matching_lulc_file, 
                    after_raster_path=file, 
                    output_raster_path=os.path.join("testing","data",f"lulc_pa_{year}_diff.tif"),
                    write_difference=True
                )
            )

        #cleanup
        self.test_outputs.extend(output_files)

    def test_reclassify_raster_with_impedance_pa_effect(self):
        """Test if the method reclassifies rasters with impedance values, specifically test for one value that is unique only to the impedance csv"""
        #TODO open impedanca csv and unique check value exists in raster

        impedance_reclass_table = os.path.join(self.impedance_dir, self.config.get('impedance'))
        impedance_df = pd.read_csv(impedance_reclass_table)
        # get the impedance value for industrial and commercial areas, which is 7 for lulc but 500 for impedance
        expected_value = impedance_df[impedance_df['type'] == "industrial and commercial areas"]['impedance'].values[0]
        self.assertEqual(expected_value, 500)

        self.wwp.reclassify_raster_with_impedance()
        impedance_files = [f for f in os.listdir(self.impedance_dir) if f.endswith('.tif')]

        #for each impedance file, check if the reclassified raster has the unique value from the impedance csv
        for impedance_file in impedance_files:
            if impedance_file.endswith("_upd.tif"):
                continue
            # Open the raster file
            raster_path = os.path.join(self.impedance_dir, impedance_file)
            ds = gdal.Open(raster_path)
            rs = ds.GetRasterBand(1)
            raster_data = rs.ReadAsArray()
            print(raster_data)

            # Check if the unique value from the impedance csv exists in the raster data
            self.assertIn(expected_value, raster_data.flatten())

            # Close the dataset
            ds = None


    def test_compute_affinity(self):
        """Test if the method computes landscape affinity."""
        affinity_files = [f for f in os.listdir(self.affinty) if f.endswith('.tif')]
        self.wwp.compute_affinity(affinity_dir=self.affinty)
        
        for file in affinity_files:
            # open file and read array
            affinity_path = os.path.join(self.affinty, file)
            ds = gdal.Open(affinity_path)
            rs = ds.GetRasterBand(1)
            affinity_data = rs.ReadAsArray().flatten()

            # Close the dataset
            ds = None 

            # get the matching impedance file
            impedance_file = file.replace('affinity', 'impedance')
            impedance_path = os.path.join(self.impedance_dir, impedance_file)
            # open impedance file and read array
            ds = gdal.Open(impedance_path)
            rs = ds.GetRasterBand(1)
            impedance_data = rs.ReadAsArray().flatten()
            # Close the dataset
            ds = None

            # Check if the affinity data is the reciprocal of the impedance data
            # excluding 0 and 9999 values
            valid_affinity = affinity_data[(affinity_data != 0) & (affinity_data != 9999)]
            valid_impedance = impedance_data[(impedance_data != 0) & (impedance_data != 9999)]

            self.assertTrue(
                np.allclose(valid_affinity, 1 / valid_impedance, atol=1e-6),
                f"Affinity data does not match reciprocal of impedance data for {file}"
            )
            

    
if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
    