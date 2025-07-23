import unittest
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch
from enrichment.lulc_enrichment_wrapper import LULCEnrichmentWrapper
from enrichment.vector_data_processor import VectorDataPreprocessor
from enrichment.lulc_data_processor import LULCDataPreprocessor

# local imports required for the tests
import yaml
#from utils import load_yaml,extract_attribute_values,get_lulc_template,read_years_from_config
from testing.testing_toolkit import check_vector_pixels_by_coordinates, check_raster_metadata, calculate_raster_difference, check_raster_min_max_values
import os
from osgeo import gdal

class TestEnrichmentWrapperProcessor(TestCase):
    @classmethod
    def setUpClass(cls):
        """Setup the test environment once before all tests"""
        #warnings.simplefilter("ignore", ResourceWarning)

        config_path = "./testing/config/config.yaml"
        with open(config_path, 'r') as file:
            cls.config = yaml.safe_load(file)


        cls.working_dir = os.path.join(os.getcwd(), 'testing')
        cls.vector_dir = os.path.join(cls.working_dir,cls.config["case_study_dir"],cls.config['vector_dir'])
        cls.years = [2012, 2017, 2022]
        cls.lulc_filepaths = {year:'./testing/data/shared/input/lulc/lulc_albera_ext_concat_{year}.tif'.format(year=year) for year in cls.years}

        cls.lew = LULCEnrichmentWrapper(
           working_dir=cls.working_dir,
           config_path=config_path,
           osm_api_type="overpass",
           threads=2,
           use_lulc_pa=True,
           verbose=True,
        )

    def test_prepare_lulc_osm_data(self):
        """
        Test the preparation of LULC and OSM data.
        1. test if the LULC data is prepared correctly
        2. test if the OSM data is prepared correctly
        """
        for year in self.years:
            self.lew.initialise_data_processors(year)
            # check if the vector data processor is initialised
            self.assertIsInstance(self.lew.vp, VectorDataPreprocessor)
            # check if the lulc data processor is initialised
            self.assertIsInstance(self.lew.lp, LULCDataPreprocessor)


    def test_buffer_vector_data(self):
        """
        Test the buffering of vector data. Creates buffered versions of roads and railways.
        1. Check if the buffered files exist.
        2. If the buffered files already exist, check if the mock is called
        """
        for year in self.years:
            self.lew.initialise_data_processors(year)
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
        """
        Test the rasterization of vector roads.
        1. Check if the rasterized roads are created for each year.
        2. Check if the rasterized roads are created with the expected road types.
        3. Check if the rasterized roads have the expected metadata.
        4. Check if the rasterized roads are different from the LULC raster.
        """
        for year in self.years:
            self.test_buffer_vector_data()
            expected_road_types = ['motorway', 'primary', 'secondary', 'tertiary','trunk']
            stressor_dict = self.lew.rasterize_vector_roads(
                year = year,
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
            raster_file = os.path.join(self.lew.stressors_dir, f"roads_{year}.vrt")
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

            # create blank raster to compare output raster with with the same metadata as the output raster
            blank_raster = raster_file.replace(f"{year}.vrt", f"{year}_blank.vrt")
            road_tiffs.append(blank_raster)  # add the blank raster to the list for cleanup

            ds = gdal.Open(raster_file)
            driver = gdal.GetDriverByName('GTiff')
            blank_ds = driver.Create(blank_raster, ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Int32)
            blank_ds.SetGeoTransform(ds.GetGeoTransform())
            blank_ds.SetProjection(ds.GetProjection())
            blank_ds.GetRasterBand(1).SetNoDataValue(0)
            blank_ds.FlushCache()
            ds = None
            
            self.assertTrue(
                calculate_raster_difference(
                    before_raster_path=blank_raster,
                    after_raster_path=raster_file,
                    output_raster_path=None,
                    write_difference=False
                )
            )

            check_raster_min_max_values(
                testing=self,
                raster_path=raster_file,
                expected_min=0,
                expected_max=self.lew.lp.lulc_codes["lulc_road"])

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
    
    def test_rasterize_vector_layers(self):
        """
        Test the rasterization of all vector layers 
        """
        for year in self.years:
            self.lew.initialise_data_processors(year)
            #rasters_temp order = vineyards, waterbodies, waterways, roads, railways
            self.rasters_temp = self.lew.rasterize_vector_layers(year,save_osm_stressors=True)
            
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

            # create blank raster to compare output raster with with the same metadata as the output raster
            blank_raster = raster_file.replace(f".tif", f"_blank.tif")
            ds = gdal.Open(raster_file)
            driver = gdal.GetDriverByName('GTiff')
            blank_ds = driver.Create(blank_raster, ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Int32)
            blank_ds.SetGeoTransform(ds.GetGeoTransform())
            blank_ds.SetProjection(ds.GetProjection())
            blank_ds.GetRasterBand(1).SetNoDataValue(0)
            blank_ds.FlushCache()
            ds = None
            
            self.assertTrue(
                calculate_raster_difference(
                    before_raster_path=blank_raster,
                    after_raster_path=raster_file,
                    output_raster_path=None,
                    write_difference=False
                )
            )
            check_raster_min_max_values(
                testing=self,
                raster_path=raster_file,
                expected_min=0,
                expected_max=self.lew.lp.lulc_codes["lulc_water"]
            )


    def test_merge_lulc_osm_data(self):
        for year in self.years:
            self.lew.initialise_data_processors(year)
            merged_lulc_path = self.lew.merge_lulc_osm_data(year = year, nodata_value=-9999, save_osm_stressors=True, cog_compress=True)
            # self.assertTrue(os.path.exists(merged_lulc_path))

            input_lulc_path = self.lulc_filepaths[year]

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

            self.assertTrue(
                calculate_raster_difference(
                    before_raster_path=self.lulc_filepaths[year],
                    after_raster_path=merged_lulc_path,
                    output_raster_path=os.path.join("testing","data","test_output","difference_raster.tif"),
                    write_difference=True
                )
            )
            # TODO check the pixel values of the merged raster (Order of burned in values: vineyard, waterbodies, waterways, roads, railways)
            # check_vector_pixels_by_coordinates(
            #     testing=self,
            #     col=1000,
            #     row=1000,
            #     tiff_path=merged_lulc_path,
            #     expected_value=self.lew.lp.lulc_codes["lulc_vineyard"]
            # )
            break


if __name__ == "__main__":
    unittest.main()
