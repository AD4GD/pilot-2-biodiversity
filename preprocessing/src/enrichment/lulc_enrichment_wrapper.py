import numpy as np

# auxiliary libraries
import subprocess
from subprocess import Popen, PIPE
import yaml
import os
from osgeo import ogr, gdal
import multiprocessing
from typer import prompt

# local modules
from utils import load_yaml,extract_attribute_values_from_gpkg,get_lulc_template,read_years_from_config
from raster_metadata import RasterMetadata
from .lulc_data_processor import LULCDataPreprocessor
from .vector_data_processor import VectorDataPreprocessor


class LULCEnrichmentWrapper():
    """
    Uses preprocessors to prepare LULC and OSM data for rasterization, 
    then rasterizes vector data and merges both rasters into a single raster dataset.
    """
    
    def __init__(self, working_dir:str, config_path:str, osm_api_type:str, threads:int, verbose:bool) -> None:
        """
        Initializes the LULC enrichment processor.

        Args:
            working_dir (str): path to the current/working directory
            config_path (str): path to the configuration file
            osm_api_type (str): type of OSM API to use (overpass or ohsome) if user vector is not provided
            verbose (bool): verbose output
        """
        self.config = load_yaml(config_path)
        self.verbose = verbose
        self.working_dir = working_dir
        self.case_study_dir = self.config.get('case_study_dir')
        self.vector_dir = os.path.join(self.working_dir,self.case_study_dir,self.config.get('vector_dir'))
        self.output_dir = os.path.join(self.working_dir,self.case_study_dir,"output")
        # make a new stressors directory to store the outputs if it doesn't exist
        self.stressors_dir = os.path.join(self.working_dir,self.case_study_dir,self.config.get('stressors_dir'))
        if not os.path.exists(self.stressors_dir):
            os.makedirs(self.stressors_dir)

        self.lulc_dir = self.config.get('lulc_dir')
        self.years = read_years_from_config(self.config)

        # create a dict of LULC files for each year
        self.lulc_filepaths = {year:get_lulc_template(self.config, year) for year in self.years}

        self.osm_api_type = osm_api_type
        self.max_threads = threads


    def initialise_data_processors(self, year:int):
        """
        Prepares the LULC and OSM data processors which handle rasterization and merging into a single raster dataset.

        Args:
            year (int): year of the data to process
        """
        ## LULC PREPROCESSING 
        self.lp = LULCDataPreprocessor(self.config, self.lulc_filepaths[year], self.working_dir)
        
        ## OSM PREPROCESSING
        self.vp = VectorDataPreprocessor(self.config, self.working_dir, self.vector_dir, year, self.lp.raster_metadata.crs_info["epsg"], self.lp.raster_metadata.is_cartesian)

    def buffer_vector_roads_and_railways(self):
        """
        Buffer vector railway and road features to be used for rasterization.
        """
        self.vp.buffer_features('railways', self.vp.vector_railways_buffered, self.vp.lulc_crs)
        self.vp.buffer_features('roads', self.vp.vector_roads_buffered, self.vp.lulc_crs)

        # check the buffered vector files
        files_to_validate = [self.vp.vector_roads_buffered, self.vp.vector_railways_buffered]
        self.vp.check_vector_geometry_validity(files_to_validate)

    def merge_lulc_osm_data(self, year:int, save_osm_stressors:bool, cog_compress:bool):
        """
        Merges the LULC and OSM data into a single raster dataset.

        Args:
            year (int): year of the data to process
            save_osm_stressors (bool): flag to save the OSM stressors to a file for impedance recalculation
            cog_compress (bool): flag to compress the output raster as a Cloud Optimised Geotiff
        """
        
        ## rasterize vector layers
        self.rasters_temp = self.rasterize_vector_layers(year, save_osm_stressors)

        # merge rasters
        lulc_upd = os.path.normpath(os.path.join(self.working_dir,self.output_dir,f'lulc_{year}_upd.tif'))
        # TODO - to inherit the initial filename of input raster
        
        if self.verbose:
            print(f"Enriched land-use/land-cover dataset(s) will be fetched to {lulc_upd}")
            self.check_raster_dimensions([self.lulc_filepaths[year], *self.rasters_temp])
        # NOTE below is an example of what we will have in the list 
        # self.rasters_temp: /data/data/output/waterbodies_2017.tif /data/data/output/waterways_2017.tif /data/data/output/roads_2017.vrt /data/data/output/railways_2017.tif

        # overwrite rasters over input dataset in the following order: waterbodies, waterways, roads, railways
        # NOTE: HARDCODED NODATA VALUE as output LULC contains only positive integer values, so 0 is the best choice
        output_data, output_ds, nodata_value = self.overwrite_raster(self.lulc_filepaths[year], *self.rasters_temp, nodata_value=0)
        print(f"FOR WRITING UPDATED LULC RASTER: {output_data, output_ds, nodata_value}")
        self.write_raster(output_data, output_ds, lulc_upd, nodata_value, cog_compress)
        # TODO - output dataset is not being assigned correctly nodatavalue - it is byte, but inherits 0 as nodatavalue from OSM stressors and -9999 from LULC stressors

    def merge_tiffs_into_vrt(self, tiffs:list, output_path:str):
        """
        Merge multiple raster datasets into a single VRT file.

        Args:
            tiffs (list): list of paths to the raster datasets
            output_path (str): path to the output VRT file

        Returns:
            None
        """
        # write the list to a new file (path to the file is ../data/list_of_tiff_files.txt)
        tiffs_filepaths = output_path.replace('.vrt', '_tiffs.txt')
        with open(tiffs_filepaths, "w") as f:
            for item in tiffs:
                f.write(item + "\n")

        gdal_command = f"""gdalbuildvrt -input_file_list {tiffs_filepaths} {output_path}"""
        try:
            subprocess.run(gdal_command, check=True, shell=True)
        except subprocess.CalledProcessError as e:
            raise e
        finally:
            # remove the list of tiff files
            os.remove(tiffs_filepaths)

    # @DeprecationWarning
    def check_raster_dimensions(self, listraster_uri:list): 
        """
        Check the dimensions of the raster datasets.

        Args:
            listraster_uri (list): list of paths to the raster datasets
        """
        for raster_path in listraster_uri:
            dataset = gdal.Open(raster_path)
            if dataset:
                width = dataset.RasterXSize
                height = dataset.RasterYSize
            else:
                raise ValueError(f"Unable to open raster file: {raster_path}")
            print(f"Dimensions of {os.path.basename(raster_path)}: {width} x {height}")


    def write_raster(self, output_data:any, output_ds:any, output_raster:str, nodata_value:int, cog_compress:bool):
        """
        Write a new raster dataset from the given data array.

        Args:
            output_data (np.array): data array to write to the raster
            output_ds (gdal.Dataset): dataset of the input raster
            output_raster (str): path to the output raster dataset
            nodata_value (int): no data value for the output raster
            cog_compress (bool): flag to compress the output raster as a Cloud Optimised Geotiff         
        """

        temp_output_raster = output_raster if not cog_compress else output_raster + "_tmp.tif"
        
        # get the driver to write a new GeoTIFF
        driver = gdal.GetDriverByName('GTiff')
        out_ds = driver.Create(temp_output_raster, output_ds.RasterXSize, output_ds.RasterYSize, 1, gdal.GDT_Byte)
    
        # set geo-transform and projection from the input raster
        out_ds.SetGeoTransform(output_ds.GetGeoTransform())
        out_ds.SetProjection(output_ds.GetProjection())

        # write the data to the output raster
        out_band = out_ds.GetRasterBand(1)
        out_band.WriteArray(output_data)

        # set nodata value 
        out_band.SetNoDataValue(nodata_value)

        # flush the data and close files
        out_band.FlushCache()
        out_ds = None  # close the file
        output_ds = None  # close the input file

        if cog_compress:
            print("Saving enriched LULC as a compressed Cloud Optimised Geotiff...")

            # open temp_raster as a GDAL dataset before passing it
            temp_ds = gdal.Open(temp_output_raster, gdal.GA_ReadOnly) 

            cog_driver = gdal.GetDriverByName("COG")
            cog_driver.CreateCopy(
                output_raster, temp_ds,
                options=['COMPRESS=LZW', 'BIGTIFF=IF_SAFER', 'OVERVIEWS=AUTO']
            )
            
            temp_ds = None
            os.remove(temp_output_raster)

        print(f"Output raster saved to {output_raster}")

    def filter_gpkg_by_attributes(self, vector_gpkg:str, layer_name:str, attribute:str, value:str, output_gpkg:str):
        """
        Create a new layer from the input layer based on the attribute value.

        Args:
            vector_gpkg (str): path to the input vector GeoPackage file
            layer_name (str): name of the layer to extract features from
            attribute (str): attribute name to filter by
            value (str): value to filter by
            output_gpkg (str): path to the output GeoPackage file

        Returns:
            str: path to the output GeoPackage file
        """
        print("Layer to access:", layer_name)
        ogr_command = f"""
            ogr2ogr -f GPKG {output_gpkg} {vector_gpkg} -sql "SELECT * FROM {layer_name} WHERE {attribute} LIKE '%{value}%'"
        """
        # DEBUG: print the command to extract the subtypes of stressors from the vector dataset
        if self.verbose:
            print(f"The following command to extract features:\n{ogr_command}")
        proc = Popen(ogr_command, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr)
        
        print(f"New layer saved to {output_gpkg}")

        # TODO - probably to move from PIPE to subprocess.run as takes more time

        # # define ogr2ogr command
        # ogr2ogr_cmd = [
        #     'ogr2ogr',
        #     '-f', 'GPKG',
        #     output_gpkg,
        #     vector_gpkg,
        #     '-dialect', 'SQLite',
        #     '-sql', sql_statement
        # ]

        # # execute ogr2ogr command through subprocess
        # subprocess.run(ogr2ogr_cmd, check=True)
        
        return output_gpkg
   
    def rasterize_vector_roads(self, year:int, output_dir:str, raster_metadata:str ,roads_gpkg:str, burn_value:int, groupby_roads:bool):
        """
        Rasterize roads vector layer to be used for enriching the LULC dataset.

        Args:
            year (int): year of the data to process
            output_dir (str): path to the output directory
            raster_metadata (RasterMetadata): object containing raster metadata (extent, cell size, etc.)
            roads_gpkg (str): path to the roads GeoPackage file
            burn_val (int): value to burn into the output raster 
            groupby_roads (bool): flag to group road types by suffix (e.g. primary, secondary, tertiary)
            
        Returns:
            dict: dictionary containing road type stressors.
        """

        #extract road types from roads geopackage

        #NOTE we can hard code the layer name since we know it is roads, but we can also extract it from the geopackage assuming there is only one layer
        # road_layer_name = [layer for layer in self.vp.vector_layer_names if 'road' in layer.lower()][0]
        road_layer_name = 'roads'
        if self.config.get('user_vector', None) is not None:
            road_types = extract_attribute_values_from_gpkg(roads_gpkg, road_layer_name, attribute='highway')
            confirm = str(prompt(
                "Type 'yes' to confirm stressor types, or enter the list of stressor (OSM highway) types from the following list of detected road types:\n ", 
                road_types,
                type=str
            )).lower()
            if confirm == "yes" or confirm == "y":
                print(f"Road types found in the input vector file: {road_types}")
            else:
                while True:
                    valid = True
                    user_input = confirm.split(",")
                    for road_type in user_input:
                        if road_type not in road_types:
                            valid = False
                            print(f"Invalid input: {road_type}")
                    if valid:
                        road_types = user_input
                        break
                    else:
                        confirm = str(prompt("Enter the list of stressor (OSM highway) types from the following list: ", road_types,type=str)).lower()
        else:
            if self.osm_api_type == "overpass":
                # extract the road types from the config file that match the road types
                road_types = self.config.get('overpass_roads', None)[0].split("highway~\"^(")[1].split(")")[0].split("|")
                print(f"Road types found in the configuration file: {road_types}")
            elif self.osm_api_type == "ohsome":
                # extract the road types from the config file that match the road types. list(map(str.strip())) will delete extra spaces
                road_types = list(map(str.strip, self.config.get('ohsome_roads', "").split("(")[2].split(")")[0].split(",")))
                print(f"Road types found in the configuration file: {road_types}")

        #group attributes by first suffix (e.g. primary, secondary, tertiary) split by '_'
        if groupby_roads:
            road_types = list(set([road_type.split('_')[0] for road_type in road_types if road_type is not None]))
            print(f"Road types to be rasterized: {road_types}")
        
        # for each road type, rasterize the roads
        road_tiffs = []

        with multiprocessing.Pool(self.max_threads) as pool:
            road_gpkgs = pool.starmap(self.filter_gpkg_by_attributes, [(roads_gpkg, road_layer_name, 'highway', road_type, os.path.join(output_dir,f'roads_{road_type}.gpkg')) for road_type in road_types])
            road_tiffs = pool.starmap(self.rasterize_vector_layer, [(raster_metadata, road_gpkg, road_gpkg.replace('.gpkg', f'_{year}.tif'), 0, burn_value, f'roads_{road_gpkg.split("_")[1].split(".")[0]}') for road_gpkg in road_gpkgs])
            pool.map(os.remove, road_gpkgs)
        
        # build a roads.vrt file to merge all road types
        self.merge_tiffs_into_vrt(road_tiffs, os.path.join(output_dir,f'roads_{year}.vrt')) 
        return {'roads':road_types}

    def rasterize_vector_layers(self, year:int, save_osm_stressors:bool=False):
        """
        Rasterize all vector layers to be used for enriching the LULC dataset.

        Args:
            year (int): year of the data to process
            save_osm_stressors (bool): flag to save the OSM stressors to a file for impedance recalculation
            
        Returns:
            list: list of paths to the rasterized layers
        """
        roads = os.path.join(self.stressors_dir,f'roads_{year}.vrt') # TO CHANGE
        railways = os.path.join(self.stressors_dir,f'railways_{year}.tif')
        waterbodies = os.path.join(self.stressors_dir,f'waterbodies_{year}.tif')
        waterways = os.path.join(self.stressors_dir,f'waterways_{year}.tif')
        vineyards = os.path.join(self.stressors_dir,f'vineyards_{year}.tif')
        rasters_temp = [vineyards, waterbodies, waterways, roads, railways] # Order is important for next steps
        
        # rasterize roads and railways from buffered geometries
        osm_impedance_stressor_types = self.rasterize_vector_roads(year, os.path.dirname(roads), self.lp.raster_metadata, self.vp.vector_roads_buffered, burn_value=self.lp.lulc_codes["lulc_road"], groupby_roads=True)
        self.rasterize_vector_layer(self.lp.raster_metadata,self.vp.vector_railways_buffered, railways, nodata_value=0, burn_value=self.lp.lulc_codes["lulc_railway"])
        # add railway to stressors (NOTE because there is no railway type processing we use None)
        osm_impedance_stressor_types['railways'] = None
        
        # we can group the other unbuffered layers with multiprocessing techniques
        process_layers = {
            'waterbodies': (waterbodies, self.lp.lulc_codes["lulc_water"]),
            'waterways': (waterways, self.lp.lulc_codes["lulc_water"]),
            'vineyards': (vineyards, self.lp.lulc_codes["lulc_vineyard"])
        }
        with multiprocessing.Pool(self.max_threads) as pool:
            rasters_temp = pool.starmap(self.rasterize_vector_layer, [(self.lp.raster_metadata, self.vp.vector_refine, output_path ,0, lulc_code, layer_name) for layer_name,(output_path,lulc_code) in process_layers.items()])

        # write osm_stressors to file
        if save_osm_stressors == True:
            # Path is hardcoded since it is a temporary file
            with open(os.path.join(self.working_dir,"config","stressors.yaml") , 'w') as file:
                yaml.dump(osm_impedance_stressor_types, file, default_flow_style=True)
            print("OSM stressors saved to stressors.yaml for impedance recalculation.")

        return rasters_temp
    
    def rasterize_vector_layer(self, lulc:RasterMetadata, vector_path:str, output_path:str, nodata_value:str, burn_value:str, layer_name:str=None):
        """
        Rasterize a vector layer to a raster dataset.

        Args:
            lulc (Raster_Properties): object containing raster properties
            vector_path (str): path to the vector dataset
            output_path (str): path to the output raster dataset
            nodata_value (str): no data value for the output raster
            burn_value (str): value to burn into the output raster
            layer_name (str): name of the layer to rasterize (optional if there is more than one layer in the input file)

        Returns:
            str: path to the output raster dataset
        """
        # open the vector data source
        data_source = ogr.Open(vector_path)
        if data_source is None:
            raise RuntimeError(f"Failed to open the vector file: {vector_path}")

        # check the number of layers and write it to the variable
        layer_count = data_source.GetLayerCount()
        
        # define gdal_rasterize command
        #TODO get extent from lulc raster
        gdal_rasterize_cmd = [
            'gdal_rasterize',
            '-tr', str(lulc.cell_size), str(lulc.cell_size),  # output raster pixel size
            '-te', str(lulc.x_min), str(lulc.y_min), str(lulc.x_max), str(lulc.y_max),  # output extent 
            '-a_nodata', str(nodata_value),  # no_data value
            '-ot', 'Int16',   # output raster data type,
            '-burn', str(burn_value),  # burn-in value
            '-at',  # all touched pixels are burned in
            vector_path,  # input vector file
            output_path  # output raster file
        ]

         # add the layer name if there are multiple layers 
        if layer_count > 1: # specify layer name if using merged geopackage as an input file
            gdal_rasterize_cmd.insert(1, '-l')
            gdal_rasterize_cmd.insert(2, str(layer_name))

        # execute gdal_rasterize command through subprocess
        subprocess.run(gdal_rasterize_cmd, check=True, capture_output=True, text=True)

        # mask out data outside the extent of the input raster
        for year in self.years:
            # DEBUG
            print(f"FOR MASKING: {output_path, self.lulc_filepaths[year], nodata_value}")
            self.mask_raster_with_raster(output_path, self.lulc_filepaths[year], nodata_value)
        
        # compress output 
        output_compressed = output_path.replace('.tif', '_compr.tif')
        gdal_translate_cmd = [
            'gdal_translate',
            output_path,
            output_compressed,
            '-co', 'COMPRESS=LZW',
            '-ot', 'Byte'
        ]
        # execute gdal_translate command through subprocess
        subprocess.run(gdal_translate_cmd, check=True)

        # rename compressed output to original
        os.remove(output_path)
        os.rename(output_compressed, output_path)

        print("Rasterized output saved to:", output_path)
        print("-" * 40)
        return output_path

    def mask_raster_with_raster(self, input_raster, mask_raster, nodata_value, output_raster:str = None):
        """Masks an input raster with a mask raster.

        Args:
            input_raster: Path to the input raster.
            mask_raster: Path to the mask raster.
            output_raster: Output raster path. If None, the input raster will be overwritten.
            nodata_value: NoData value for the output raster.
        """

        # open input and mask rasters
        in_ds = gdal.Open(input_raster)
        mask_ds = gdal.Open(mask_raster)

        # get raster properties
        in_band = in_ds.GetRasterBand(1)
        mask_band = mask_ds.GetRasterBand(1)
        mask_nodata_val = mask_band.GetNoDataValue()
        print(f"Nodata value of the masking raster dataset: {mask_nodata_val}")

        out_driver = gdal.GetDriverByName('GTiff')
        if output_raster is None:
            out_ds = gdal.Open(input_raster, gdal.GA_Update)
        else:
            out_ds = out_driver.Create(output_raster, in_ds.RasterXSize, in_ds.RasterYSize, 1, in_band.DataType)
            out_ds.SetProjection(in_ds.GetProjection())
            out_ds.SetGeoTransform(in_ds.GetGeoTransform())
        out_band = out_ds.GetRasterBand(1)

        # create a mask array from the mask raster
        mask_data = mask_band.ReadAsArray()
        mask_data[mask_data == mask_nodata_val] = nodata_value

        # apply the mask to the input raster
        in_data = in_band.ReadAsArray()
        # mask out the input data where the mask is nodata, otherwise keep the input data
        out_data = np.where(mask_data == nodata_value, nodata_value, in_data) # TODO - to rewrite to avoid multiplying mask (LULC) by rasterised vector features

        # write the masked data to the output raster
        out_band.WriteArray(out_data)
        out_band.SetNoDataValue(nodata_value)
        out_ds.FlushCache()

        # close datasets
        in_ds = None
        mask_ds = None
        out_ds = None

    # function to overwrite values from input raster by multiple rasters
    def overwrite_raster(self, base_raster:str, *rasters:str, nodata_value: int):
        """
        Merge multiple rasters by overwriting values from the base raster with valid data from other rasters.

        Args:
            base_raster (str): path to the base raster dataset
            *rasters (str): paths to other raster datasets to be merged
            nodata_value (int): no data value to be applied for the output raster
        
        Returns:
            np.array: merged raster dataset
            gdal.Dataset: dataset of the base raster
            int: nodata value of the output raster
        """
        # open the input raster and read it
        base_ds = gdal.Open(base_raster)
        base_band = base_ds.GetRasterBand(1)
        base_data = base_band.ReadAsArray().astype(np.float32)
        
        # get nodata value for the input raster
        if nodata_value is None:  # if nodata value is not defined, set 0 as a default
            nodata_value = 0
        base_data[base_data == nodata_value] = np.nan  # replace nodata value with nan for processing
        print(f"Nodata value of the input raster dataset: {nodata_value}")
        
        # iterate over other rasters
        for raster in rasters:
            ds = gdal.Open(raster)
            band = ds.GetRasterBand(1)
            data = band.ReadAsArray().astype(np.float32)
            current_nodata = band.GetNoDataValue()
            if current_nodata is None:  # handle missing nodata value
                current_nodata = 0
            data[data == current_nodata] = np.nan  # replace nodata with nan for processing
            
            # overwrite values in base_data where current raster has valid data
            mask = ~np.isnan(data)
            base_data[mask] = data[mask]
        
        # after processing, replace NaNs with the nodata value before saving
        base_data[np.isnan(base_data)] = nodata_value
        
        return base_data, base_ds, nodata_value
    
if __name__ == "__main__":
    config_path = os.path.join(os.getcwd(),"config", "config.yaml")
    lew = LULCEnrichmentWrapper(os.getcwd(),config_path, osm_api_type="overpass", threads=4, verbose=True)
    # prepare and merge LULC and OSM data
    lew.initialise_data_processors(lew.years[0])
    #buffer vector roads and railways
    lew.buffer_vector_roads_and_railways()
    # merge LULC and OSM data
    lew.merge_lulc_osm_data(lew.years[0], save_osm_stressors=True, cog_compress=False)
    print("LULC and OSM data processing complete.")