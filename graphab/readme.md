## **Habitat connectivity calculation (Graphab): application**

### INSTALLATION
Graphab itself is a self-contained application, but a few libraries are required additionally to harmonise its outputs.
This tool can be run through the pre-defined Docker container. All large INPUT AND OUTPUT datasets (.tif and .gpkg) are not included in the image (see `.dockerignore`)..
However, these datasets are accessible from the build context through the `volumes` in `docker-compose.yaml`configuration.
1. Build image: `docker-compose build` or `docker-compose build --no-cache --progress=plain`
2. Run container w: `docker run -it -v $(pwd):/src graphab` (`-v` option is required to mount container with local directory and access ignored datasets)

To build container: `docker-compose up`
To reset image: `docker-compose down`

### EXECUTION
Processing happens through:
1. The .jar application of Graphab (currently used version 3.0.1)
2. [Wrapping job script](graphab_wrapper.sh) and underlying job [graphab_job_loop.sh], defining the commands which are relevant for local and regionals connectivity research
3. [The configuration file(s)](config/), defining ecological parameters and commands scheduled to run. It is possible to save as many configuration files as user need
(to run series of case studies), but they always need to specify the name of the configuration file in the beginning of the [Graphab job](graphab_job.sh)
Once all conditions are satisfied, the Graphab job can be executed through the command line: `.\graphab_job.sh`
4. Python scripts to harmonise processing outputs, calculate stats, visualise trends, and also to access/read/upload data to [MinIO](https://minio-ad4gd-console.dashboard-siba.store/) cloud-based data object storage.

Currently, all steps can be run as a single data pipeline via one command in Dockerfile:
`CMD ["python3" , "main.py" , {case_study} , {habitat1,habitat2,habitat3}]`

For example, to run processing for all habitats in Catalonian case study, CMD should be replaced with the following:
`CMD ["python3" , "main.py" , "cat_aggr_buf_390m_test" , "forest,shrubland,woody,herbaceous,aquatic"]`

**TO RUN THE FULL CYCLE WITHOUT DOCKERFILE** (if input data are prepared for each case study):
1. In the container, run `nohup ./graphab_wrapper.sh {case_study}`. It will create connectivity outputs for the case study grouped by habitats (or so-called sub case studies).
**TODO**: implement case_study . Multiple names of case studies are supported (list them with comma), but it is generally not recommended to run this command with multiple case studies, as Graphab computations might take significant amount of time even for one case study.
Example: ``nohup ./graphab_wrapper.sh cat_aggr`
Multiple names of case studies are supported (list them with comma.)
2. In the container, run `nohup python3 ./glob.py {case_study}` to harmonise global connectivity indices and create statistics in CSV, where `{case_study}` is the name of case study (multiple names are supported by listing with comma).
Example: `python3 ./glob.py cat_aggr`
*NOTE: We do not implement the argument to choose from the available habitats as this command is usually quickly executed for all habitats*
**TODO**: `python3 ./glob.py {case_study} --combine_case_studies"` to combine all stats from multiple case studies
3. In the container, run `nohup python3 ./join_gpkg2tif.py {case_study}` to translate the part of outputs with global indices to GeoTIFF format. It will create one-band GeoTIFF files for each index computed previously, for all case studies specified (and for all habitats). Multiple names of case studies are supported (list them with comma).
Example: 
*NOTE: We do not implement the argument to choose from the available habitats as this command is usually quickly executed for all habitats*
Example: `nohup python3 ./join_gpkg2tif.py cat_aggr`
4. In the container, run `nohup python3 ./postproc.py {case_study}` to optimise outputs that need to be clipped by the extent of input datasets, masked by no-data values from input datasets, compressed and transformed in Cloud Optimised Geotiff. Multiple names of case studies are supported (list them with comma.)
Example: `nohup python3 ./postproc.py cat_aggr`
*NOTE: We do not implement the argument to choose from the available habitats as this command is usually quickly executed for all habitats*

**PENDING:**
**TODO** - to clean and rerun 'cat_aggr'
**TODO** - in 'cat_aggr' run corridors with 0 beta value for 'herbaceous'

**NOTE:** if you need to create impedance dataset based on the reclassification table with LULC values and corresponding values, use another [stand-alone script](impedance_csv2tif.py):
`nohup python3 ./impedance_csv2tif.py {case_study} {habitat1},{habitat2},{habitat3}`. It supports multiple habitats, for example:
`nohup python3 ./impedance_csv2tif.py cat_aggr_30m forest,herbaceous,woody,aquatic`

To interactively browse through the processing, attach `& tail -f nohup.out` to your command, for example: 
`nohup python3 ./impedance_csv2tif.py cat_aggr_30m forest,herbaceous,woody,aquatic & tail -f nohup.out`
nohup processes cannot be stopped through Ctrl+C in command line (only by killing process) 

`nohup python3 ./join_gpkg2tif.py cat_aggr_buf_390m & tail -f nohup_2.out`
nohup python3 ./join_gpkg2tif.py cat_aggr_buf_390m > nohup_2.out 2>&1 & tail -f nohup_2.out

#### GRAPHAB JAVA APPLICATION
According to the Graphab manual v.3.0:
"Avoid blank spaces in the project's name and the project's elements!". Otherwise, underlying commands will be corrupted.

#### CONFIGURATION: MAIN PARAMETERS
If you already defined the case study, mapping of habitat names in the configuration file, and corresponding values in the input LULC dataset, to run Graphab correctly, check the following:
- the name of the case study. Do you use the valid one?
- in the corresponding [configuration files](config/) check the following keys:
	- `case_study`
	- `sub_case_study`
	- `habitat_name`
	*if your sub case studies are built on the habitat names, `habitat_name` corresponds with `sub_case_study`. However, they might be different, for example, if `sub_case_study` are built for species. 
- in the configuration file check the `years` and `commands` if you just need subsets of output data.
- habitat names when running Python scripts

#### CONFIGURATION: OTHER PARAMETERS
- `XMS` and `XMX` are the initial and maximum heap size used to run Java applications. The maximum can be defined as the machine RAM minus 1 GB.
Changes in these parameters haven't lead to any significant performance improvement yet, but they reduce the chances of 'Java heap space' error.
- `PROC_NUM` parameter can be chosen empirically for your commands. For example, on 8-CPU machine, `PROC_NUM=7` for case study of Catalonia is facing `Java heap space`, whereas 6 or 5 is usually fine for these commands.
For the details, see the [Graphab forum](https://thema.univ-fcomte.fr/flarum/d/15-error-javalangoutofmemoryerror-java-heap-space).
**NOTE**: `XMS`, `XMX` and `PROC_NUM` parameters must be specified in the `.env` file, for example:
> XMS=10G \
XMX=20G \
PROC_NUM=6

- `con8` option is disabled as it is computes connectivity to 8 neigbouring pixels and overloads the computation.
- `mpi` parameter is disabled (can be used only on computer clusters supporting Java for OpenMPI).
The parameters listed above might be tweaked if Graphab is run on a HPC cluster.

**Status of case studies in `data\`:**

|  Case study alias  |Spatial extent| Temporal extent| LULC types|  Buffered  | Updated with OSM| Impedance validity/edge effect|Data compl|
|--------------------|--------------|----------------|-----------|------------|-----------------|-------------------------------|----------|
|      'albera'      | NE Catalonia |   1987-2022    |    24     |   no       |       no        |no edge effect (correct)       |    +     | 
|    'albera_buf'    | NE Catalonia |   1987-2022    |    24     |   yes      |       no        |no edge effect (correct)       |    +     |
|  'albera_buf_upd'  | NE Catalonia |   2012-2022    |    24     |   yes      |       yes       |no edge effect (to compute)    |    +-    |
|    'albera_upd'    | NE Catalonia |   2012-2022    |    24     |   no       |       yes       |valid edge effect              |    +     |
|     'cat_aggr'     |   Catalonia  |   1987-2022    |    7      |   no       |       no        |no edge effect (correct)       |    +     |
| 'cat_aggr_buf_upd' |   Catalonia  |   2012-2022    |    7      |   yes      |       yes       |                               |    -     |
| 'cat_aggr_buf_30m' |   Catalonia  |   2012-2022    |    7      |yes (2500 m)|       no        |no edge effect (correct)       |    +     |
|'cat_aggr_buf_390m' |   Catalonia  |   2012-2022    |    7      |yes (2500 m)|       no        |no edge effect (correct)       |    +     |
|   'cat_aggr_upd'   |   Catalonia  |   2012-2022    |    7      |     no     |       yes       |                               |    -     |
|      'cat_ext'     |   Catalonia  |   1987-2022    |    24     |     no     |       no        |map values - to use for turtle |    +-    |
|    'cat_ext_upd'   |   Catalonia  |   2012-2022    |    24     |     no     |       yes       |map values betw LULC and imp ? |    -     |


## Acknowledgements

The work has been co-funded by the European Union and the United Kingdom under the 
Horizon Europe [AD4GD Project](https://www.ogc.org/initiatives/ad4gd/).