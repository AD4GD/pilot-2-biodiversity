import unittest
from unittest import TestCase
from enrichment.vector_data_processor import VectorDataPreprocessor
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

class TestVectorDataProcessor(TestCase):
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
        # cls.assertTrue(os.path.exists(lulc_filepath))
        raster_metadata = RasterMetadata.from_raster(cls.lulc_filepath)
        cls.vp = VectorDataPreprocessor(
            cls.config, 
            cls.working_dir, 
            cls.vector_dir, 
            cls.year, 
            raster_metadata.crs_info["epsg"], 
            raster_metadata.is_cartesian
        )
        pass

    def test_init(self):
        print("Testing the VectorDataPreprocessor class")
        self.assertIsInstance(obj=self.vp, cls=VectorDataPreprocessor)
    
    def test_load_auxillary_data(self):
        expected = os.path.join(self.working_dir, self.vector_dir, f"osm_merged_{self.year}.gpkg")
        self.assertEqual(
            self.vp.load_auxillary_data(self.vp.current_dir, self.vp.vector_dir, self.vp.year)
            , expected
        )
    
    def test_check_vector_data(self):
        expected = sorted(['roads', 'waterbodies', 'waterways', 'vineyards','railways'])
        self.assertEqual(
            sorted(self.vp.check_vector_data_crs(self.vp.vector_refine, self.vp.lulc_crs))
            , expected
        )

    def test_buffer_features_railways(self):
        merged_gpkg = os.path.join(self.working_dir, self.vector_dir, f"osm_merged_{self.year}.gpkg")
        layer_name = 'railways'
        # open the datasource and pick the first feature take note of the id and area of the feature
        ds = ogr.Open(merged_gpkg)
        # get railway layer
        layer = ds.GetLayerByName(layer_name)
        feature = layer.GetNextFeature()
        feature_id = feature.GetFID()
        geom_area = feature.GetGeometryRef().GetArea()
        # close the datasource
        ds = None

        self.vp.buffer_features('railways', self.vp.vector_railways_buffered, self.vp.lulc_crs)
  
        #check if the buffered files exist in the directory
        self.assertTrue(os.path.exists(self.vp.vector_railways_buffered))
        #check if the buffered files are not empty
        self.assertTrue(os.path.getsize(self.vp.vector_railways_buffered) > 0)

        # open the datasource and check if the buffer was applied
        ds = ogr.Open(self.vp.vector_railways_buffered)
        layer = ds.GetLayer()
        #get the feature with the same id as the one we picked earlier
        buffered_feature = layer.GetFeature(feature_id)
        buffered_geom = buffered_feature.GetGeometryRef().GetArea()
        # close the datasource
        ds = None

        self.assertGreater(buffered_geom, geom_area)
    
        #clean up: delete the buffered files
        os.remove(self.vp.vector_railways_buffered)
        # os.remove(self.vp.vector_roads_buffered)

    def test_buffer_features_roads(self):
        merged_gpkg = os.path.join(self.working_dir, self.vector_dir, f"osm_merged_{self.year}.gpkg")
        layer_name = 'roads'
        # open the datasource and pick the first feature take note of the id and area of the feature
        ds = ogr.Open(merged_gpkg)
        # get railway layer
        layer = ds.GetLayerByName(layer_name)
        feature = layer.GetNextFeature()
        feature_id = feature.GetFID()
        geom_area = feature.GetGeometryRef().GetArea()
        # close the datasource
        ds = None

        self.vp.buffer_features('roads', self.vp.vector_roads_buffered, self.vp.lulc_crs)
  
        #check if the buffered files exist in the directory
        self.assertTrue(os.path.exists(self.vp.vector_roads_buffered))
        #check if the buffered files are not empty
        self.assertTrue(os.path.getsize(self.vp.vector_roads_buffered) > 0)

        # open the datasource and check if the buffer was applied
        ds = ogr.Open(self.vp.vector_roads_buffered)
        layer = ds.GetLayer()
        #get the feature with the same id as the one we picked earlier
        buffered_feature = layer.GetFeature(feature_id)
        buffered_geom = buffered_feature.GetGeometryRef().GetArea()
        # close the datasource
        ds = None

        self.assertGreater(buffered_geom, geom_area)
    
        #clean up: delete the buffered files
        os.remove(self.vp.vector_roads_buffered)

#  def test_buffer_features(self):

#         # open the datasource and pick the first feature take note of the id and area of the feature
#         ds = ogr.Open(self.vp.vector_railways)
#         layer = ds.GetLayer()
#         feature = layer.GetNextFeature()
#         feature_id = feature.GetFID()
#         geom_area = feature.GetGeometryRef().getArea()
#         #
#         self.vp.buffer_features('railways', self.vp.vector_railways_buffered, self.vp.lulc_crs)
#         self.vp.buffer_features('roads', self.vp.vector_roads_buffered, self.vp.lulc_crs)

#         #check if the buffered files exist in the directory
#         self.assertTrue(os.path.exists(self.vp.vector_railways_buffered))
#         self.assertTrue(os.path.exists(self.vp.vector_roads_buffered))

#         #check if the buffered files are not empty
#         self.assertTrue(os.path.getsize(self.vp.vector_railways_buffered) > 0)
#         self.assertTrue(os.path.getsize(self.vp.vector_roads_buffered) > 0)


#         # open the datasource and check if the buffer was applied
#         ds = ogr.Open(self.vp.vector_railways_buffered)
#         layer = ds.GetLayer()
#         feature = layer.GetNextFeature()
#         geom = feature.GetGeometryRef()
#         self.assertGreaterEqual(geom.GetGeometryCount(), 1)
#         self.assertEqual(geom.GetGeometryName(), 'MULTILINESTRING')

#         # check the size of the polygon
#         self.assertGreaterEqual(geom.GetArea(), 0.0)


#         # check if the buffered files are in the correct CRS
#         # rm = RasterMetadata.from_vector(self.vp.vector_railways_buffered)
        
#         #clean up: delete the buffered files
#         # os.remove(self.vp.vector_railways_buffered)
#         # os.remove(self.vp.vector_roads_buffered)