import os
import requests
import subprocess
from rich import print as rprint
# local imports 
from .pa_processor import PAProcessor

class PAProcessorWrapper:
    """
    This class retrieves and processes protected areas for multiple countries and utilizes the PA processor class to merge them into individual GeoJSON files for each country.
    """

    def __init__(self, countries:list[str], api_url:str, token:str, marine:str, output_dir:str) -> None:
        """
        Initialize the PA_Processor_Wrapper class.

        Args:
            countries (list): A list of country codes.
            api_url (str): The API endpoint URL.
            token (str): The API token.
            marine (str): The marine area boolean value.
            output_dir (str): The path to the directory where the GeoJSON files will be saved.
        """
        self.api_url = api_url
        self.token = token
        self.marine = marine
        self.countries = countries
        self.output_dir = output_dir
        self.processors = {country: PAProcessor(country) for country in countries}

    def process_all_countries(self, skip_fetch:bool, retry_limit:int=3) -> None:
        """
        Fetches all PAs for each country and processes them into a single GeoJSON file.

        Args:
            skip_fetch (bool): A boolean value to skip fetching the PAs if they have already been fetched
            retry_limit (int): The number of times to retry fetching the data if a server error occurs.
        """
       
        for country in self.countries:
            protected_area_data = []
            if skip_fetch:
                # check if the GeoJSON file already exists
                geojson_file = os.path.join(self.output_dir, f"{country}_protected_areas.geojson")
                if os.path.exists(os.path.join(self.output_dir, geojson_file)):
                    print(f"GeoJSON file already exists for {country}, therefore skipping fetch")
                    #remove the processor for the country
                    del self.processors[country]
                    continue

            # else we fetch the PA data for the country until we get an empty response
            page = 0
            page_logs = {}
            while True:
                url = self.api_url.format(country=country, token=self.token, marine=self.marine)
                url += f"&page={page}"
                response = requests.get(url)
                #if the error is client side, we should stop the loop
                if response.status_code >= 400 and response.status_code < 500:
                    raise Exception(f"Error ({response.status_code}):, {response.text}")
                #if it's a server side error, we should try this page again up to retry_limit times
                elif response.status_code >= 500:
                    if page_logs[page] > retry_limit:
                        rprint(f"[bold red] Failed to fetch data for {country} at page {page} after 3 attempts [/bold red]")
                        rprint(f"[bold yellow] Skipping to next page [/bold yellow]")
                        page += 1
                        continue
                
                #if the response is successful, we should process the data
                elif response.status_code == 200:
                    data = response.json()
                    protected_areas = data["protected_areas"]
                    if len(protected_areas) == 0:
                        print(f"No protected areas found for {country}")
                        break # exit the loop if no protected areas are found
                    else:
                        protected_area_data.append(data)
                        page += 1
                        continue
                #TODO What should be done if we get any other codes?

            # combine all the protected areas into a single feature collection / GeoJSON
            for data in protected_area_data:
                self.processors[country].add_PA_to_feature_collection(data["protected_areas"]) 

    def save_all_country_geoJSON(self) -> list[str]:
        """
        Saves all country GeoJSON files to the export directory.

        Returns:
            geojson_filepaths (list): A list of file paths to the saved GeoJSON files.
        """
        
        geojson_filepaths = []
        for country in self.countries:
            pa_processor = self.processors.get(country, None)
            if pa_processor is not None:
                geojson_filepaths.append(pa_processor.save_to_file(self.output_dir))
        return geojson_filepaths
    

    def merge_geojsons_to_geopackage(self, geojson_filepaths:list[str], output_file:str) -> str:
        """
        Merges all GeoJSON files into a single GeoPackage file with different layers for each country.

        Args:
            geojson_filepaths (list): A list of GeoJSON file paths.
            output_file (str): The name of the output GeoPackage file.
        
        Returns:
            str: The path to the merged GeoPackage file.
        """
        # define the output merged GeoPackage file
        gpkg = os.path.join(self.output_dir, output_file)
        # remove GeoPackage if it already exists
        if os.path.exists(gpkg):
            os.remove(gpkg)

       # loop through the GeoJSON files and convert them to a geopackage
        for geojson_file in geojson_filepaths:
            # writes layer name as the first name from geojson files
            layer_name = os.path.splitext(os.path.basename(geojson_file))[0]
            # use ogr2ogr to convert GeoJSON to GeoPackage
            subprocess.run([
                "ogr2ogr", "-f", "GPKG", "-append", "-nln", layer_name, gpkg, geojson_file
            ]) 

        return gpkg