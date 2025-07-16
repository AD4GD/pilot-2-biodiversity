import unittest
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch
from enrichment.lulc_enrichment_wrapper import LULCEnrichmentWrapper
from enrichment.vector_data_processor import VectorDataPreprocessor
from enrichment.lulc_data_processor import LULCDataPreprocessor

# local imports required for the tests
import yaml
#from utils import load_yaml,extract_attribute_values,get_lulc_template,read_years_from_config
from testing.testing_toolkit import check_vector_pixels, check_raster_metadata, calculate_raster_difference
import os

class TestLulcDataProcessor(TestCase):
    @classmethod
    def setUpClass(cls):
        """Setup the test environment once before all tests"""
        #warnings.simplefilter("ignore", ResourceWarning)

        config_path = "./config/config.yaml"
        cls.lew = LULCEnrichmentWrapper(
           working_dir=os.getcwd(),
           config_path=config_path,
           osm_api_type="overpass",
           threads=2,
           use_lulc_pa=True,
           verbose=True,
        )

        with open(config_path , 'r') as file:
            cls.config = yaml.safe_load(file)
        cls.working_dir = os.getcwd()
        cls.vector_dir = os.path.join(cls.working_dir,cls.config["case_study_dir"],cls.config['vector_dir'])
        cls.year = 2017
        cls.lulc_filepath = './data/shared/input/lulc/lulc_albera_ext_concat_{year}.tif'.format(year=cls.year)

    def test_prepare_lulc_osm_data(self):
        self.lew.initialise_data_processors(self.year)
        # check if the vector data processor is initialised
        self.assertIsInstance(self.lew.vp, VectorDataPreprocessor)
        # check if the lulc data processor is initialised
        self.assertIsInstance(self.lew.lp, LULCDataPreprocessor)

    def test_buffer_vector_data(self):
        self.lew.initialise_data_processors(self.year)
        # NOTE if buffer exists, then use mocked buffer instead of creating a new one
        if os.path.exists(self.lew.vp.vector_roads_buffered) and os.path.exists(self.lew.vp.vector_railways_buffered):
            # check if the buffer_features method is called
            with patch.object(VectorDataPreprocessor, "buffer_features") as mocked_buffer:
                self.lew.buffer_vector_roads_and_railways()
                mocked_buffer.assert_called()
        else:
            self.lew.buffer_vector_roads_and_railways()
            # assert the buffered files exist
            self.assertTrue(os.path.exists(self.lew.vp.vector_roads_buffered))
            self.assertTrue(os.path.exists(self.lew.vp.vector_railways_buffered))



    def test_rasterize_vector_roads(self):
        self.test_buffer_vector_data()
        expected_road_types = ['motorway', 'primary', 'secondary', 'tertiary','trunk']
        stressor_dict = self.lew.rasterize_vector_roads(
            year = self.year,
            output_dir = self.lew.stressors_dir,
            raster_metadata= self.lew.lp.raster_metadata,
            roads_gpkg = self.lew.vp.vector_roads_buffered,
            burn_value = self.lew.lp.lulc_codes["lulc_road"],
            groupby_roads=True
        )
        # check if each file exists
        # loop through directory and get all road tiffs
        road_tiffs = [f for f in os.listdir(self.lew.stressors_dir) if "roads" in f]
        self.assertTrue(len(road_tiffs) > 0)
        # check if the road types are as expected
        self.assertEqual(sorted(stressor_dict["roads"]), sorted(expected_road_types))

        # check the metadata of the raster
        road_tiff = road_tiffs[0]
        raster_file = os.path.join(self.lew.stressors_dir, road_tiff)
        check_raster_metadata(
            self,
            raster_file,
            expected_nodata=0,
            expected_cell_size=30,
            expected_is_cartesian=True,
            expected_x_min=486435,
            expected_y_min=4683645,
            expected_x_max=517005,
            expected_y_max=4705995
        )

        # check the pixel value of the raster is correct.
        # get a specific pixel
        col = 851
        row = 386
        # test the pixel value
        check_vector_pixels(self,col, row, raster_file, self.lew.lp.lulc_codes["lulc_road"])

        # clean up - delete the road tiffs
        for road_tiff in road_tiffs:
            os.remove(os.path.join(self.lew.stressors_dir, road_tiff))

    def test_rasterize_one_vector_layer(self):
        self.test_buffer_vector_data()
        output_path = os.path.join(self.lew.stressors_dir, "test_roads.tif")
        self.lew.rasterize_vector_layer(
            self.lew.lp.raster_metadata,
            self.lew.vp.vector_roads_buffered,
            output_path=output_path,
            nodata_value=0,
            burn_value=self.lew.lp.lulc_codes["lulc_road"],
            layer_name="roads"
        )
        self.assertTrue(os.path.exists(output_path))
        # clean up
        os.remove(output_path)
        

    # def test_
    
    def test_rasterize_vector_layers(self):
        """
        Test the rasterization of all vector layers 
        """
        self.lew.initialise_data_processors(self.year)
        #rasters_temp order = vineyards, waterbodies, waterways, roads, railways
        self.rasters_temp = self.lew.rasterize_vector_layers(self.year,save_osm_stressors=True)
        
        # loop through rasters_temp and check if they exist
        for raster_path in self.rasters_temp:
            self.assertTrue(os.path.exists(raster_path))

        # check the metadata of the first raster (waterbodies)
        raster_file = self.rasters_temp[2]
        self.assertIn("waterways", raster_file)
        check_raster_metadata(
            self,
            raster_file,
            expected_nodata=0,
            expected_cell_size=30,
            expected_is_cartesian=True,
            expected_x_min=486435,
            expected_y_min=4683645,
            expected_x_max=517005,
            expected_y_max=4705995
        )
        check_vector_pixels(self,col=511, row=324, tiff_path=raster_file, expected_value=self.lew.lp.lulc_codes["lulc_water"])


    def test_merge_lulc_osm_data(self):
        self.lew.initialise_data_processors(self.year)
        merged_lulc_path = self.lew.merge_lulc_osm_data(year = self.year, nodata_value=-9999 ,save_osm_stressors=True, cog_compress=True)
        # self.assertTrue(os.path.exists(merged_lulc_path))

        input_lulc_path = self.lulc_filepath

        # compare the raster metadata of the input and merged rasters
        check_raster_metadata(
            self,
            input_lulc_path,
            expected_nodata=-9999.0,
            expected_cell_size=30,
            expected_is_cartesian=True,
            expected_x_min=486435,
            expected_y_min=4683645,
            expected_x_max=517005,
            expected_y_max=4705995
        )
        check_raster_metadata(
            self,
            merged_lulc_path,
            expected_nodata=-9999,
            expected_cell_size=30,
            expected_is_cartesian=True,
            expected_x_min=486435,
            expected_y_min=4683645,
            expected_x_max=517005,
            expected_y_max=4705995
        )

        # TODO test share of pixels
        self.assertTrue(
            calculate_raster_difference(
                before_raster_path=self.lulc_filepath,
                after_raster_path=merged_lulc_path,
                output_raster_path=os.path.join("testing","data","difference_raster.tif"),
                write_difference=True
            )
        )


if __name__ == "__main__":
    unittest.main()
