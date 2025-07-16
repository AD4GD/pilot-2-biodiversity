import subprocess
import os
from rich import print

class LulcPaRasterSum():

    def __init__(self, 
        output_path:str,
        lulc_dir:str,
        lulc_template:str,
        pa_path:str, 
        use_yearly_pa_rasters:bool,
    ):
        """
        Initialize the combine_rasters class

        Args:
            output_path (str): The path to the output directory to store the combined LULC and PA rasters.
            lulc_dir (str): The path to the LULC raster data directory.
            lulc_template (str): The template lulc file (to filter files for only this case study)
            pa_path (str): The path to the PA raster data.
            use_yearly_pa_rasters (bool): Use yearly PA rasters.
        """
        
        self.lulc_dir = lulc_dir
        self.lulc_template = lulc_template
        self.lulc_upd = lulc_template.replace("{year}.tif", "pa_{year}.tif")
        self.use_yearly_pa_rasters = use_yearly_pa_rasters
        self.output_path = self.make_directory_if_not_exists(os.path.join(output_path))
        self.pa_path = self.make_directory_if_not_exists(pa_path)

    def make_directory_if_not_exists(self, path:str):
        """
        Make a directory if it does not exist

        Args:
            path (str): The path to the directory

        Returns:
            str: The path to the directory
        """
        if not os.path.exists(path):
            os.makedirs(path)
        return path
    
    def assign_no_data_to_pa_raster(self, year:int):
        """
        Reassign no data values to the PA raster data as temporary files

        Args:
            year (int): The year of PA data for which to assign no data values
        Returns:
            str: The path to the temporary PA raster file with no data values assigned
        """
        if self.use_yearly_pa_rasters:
            # check if matching year pa file exists
            pa_file = os.path.join(self.pa_path, f"pa_{year}.tif")
        else:
            pa_file = os.path.join(self.pa_path, "pa_multi_year.tif")

        # make a temp pa_file with null no data values
        temp_pa_file = os.path.join(self.pa_path, f"pa_{year}_temp.tif")
        gdal_command = f"""
        gdal_translate -a_nodata none -co COMPRESS=LZW -co TILED=YES {pa_file} {temp_pa_file}
        """
        subprocess.run(gdal_command, shell=True)

        return temp_pa_file

    def combine_pa_lulc(self, keep_temp_files:bool=False) -> list[str]:
        """
        Combine the LULC and PA raster data

        Args:
            keep_temp_files (bool): Keep the temporary files

        Returns:
            list[str]: List of output file paths for the combined LULC and PA rasters
        """
        lulc_files = os.listdir(self.lulc_dir)
        # filter files for the case study
        lulc_files = [f for f in lulc_files if self.lulc_template.split("_{year}.tif")[0] in f.split("_{year}.tif")[0]]
        lulc_outputs = []
        
        for lulc_file in lulc_files:
            # get PA file for the year or use multi-year PA file
            year = lulc_file.split("_")[-1].split(".")[0]
            pa_file = self.assign_no_data_to_pa_raster(year)

            # get no data values assigned to the lulc file
            lulc_file = os.path.join(self.lulc_dir, lulc_file)
            if not os.path.exists(lulc_file):
                raise FileNotFoundError(f"LULC file for year {year} does not exist: {lulc_file}")
            
            # get no_data of lulc file
            gdal_command = f"gdalinfo {lulc_file} | grep 'NoData Value'"
            result = subprocess.run(gdal_command, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to get NoData Value from LULC file: {lulc_file}")
            else:
                no_data_value = result.stdout.split(":")[-1].split("=")[-1].strip()

            if os.path.exists(pa_file):
                lulc_pa_sum_file = os.path.join(self.output_path, self.lulc_upd.format(year=year))
                gdal_command = " ".join([
                    "gdal_calc.py --overwrite --calc 'A+B' --format GTiff",
                    f"--NoDataValue {no_data_value} --type Int32",
                    f"-A {lulc_file}",
                    f"--A_band 1 -B {pa_file}",
                    f"--outfile {lulc_pa_sum_file}",
                    "--co COMPRESS=LZW --co TILED=YES"
                ])
                subprocess.run(gdal_command, shell=True)
                print(f"[green] Raster sum complete for year: {year} [green]")
                lulc_outputs.append(lulc_pa_sum_file)
            else:
                raise FileNotFoundError(f"PA file for year {year} does not exist")
            
            # remove the temp files
            if keep_temp_files == False:
                subprocess.run(f"rm -rf {pa_file}", shell=True)

        return lulc_outputs


# Example usage
if __name__ == "__main__":
    from utils import load_yaml
    working_dir = os.getcwd()
    config = load_yaml("config/config.yaml")
    case_study_dir = str(config.get("case_study_dir"))
    case_study = case_study_dir.split("/")[-1]
    lulc_template = config.get("lulc")

    lprs = LulcPaRasterSum(
        output_path=os.path.join(working_dir,config["lulc_pa_dir"]),
        lulc_dir=config.get("lulc_dir"),
        lulc_template = config.get("lulc"),
        pa_path=os.path.join(working_dir, case_study_dir, "output","protected_areas","pa_rasters"),
        use_yearly_pa_rasters=False,
    )

    lprs.combine_pa_lulc()