<p align="center">
<img alt="A schematic diagram of the dataflow in pilot 2" src="https://github.com/user-attachments/assets/68a1d122-1d66-4c5f-a154-7063aeb419be">
</p>

This repository is dedicated to the Pilot 2 of the AD4GD project. <br />
- ***Preprocessing*** sub-repository is devoted to the preprocesing of the input raster land-use/land-cover (LULC) data (including Deliverables 6.1, section 6.7). Protected areas from World Database on Protected areas are integrated into preprocessing workflow to consider their importance for connecting habitats. <br />
- ***Graphab*** sub-repository contains second version of dockerised Graphab Java application in order to be deployed on the HPC cluster to ensure consistency of environment and to allow the workflow to be run reliably either on a user’s machine or as an open service module (Deliverables 6.1, section 6.7). <br />
- ***GBIF*** sub-repository is focused on the analysis of existing GBIF data (quering, access, provenance and quality of records), corresponding with the Deliverables 6.1 (section 4.6.3, GBIF ingestion). The actual integration of GBIF data with other sources for target species is analysed [here](https://github.com/AD4GD/pilot-2-gbif-iucn). <br />

## Acknowledgements

The work has been co-funded by the European Union and the United Kingdom under the 
Horizon Europe [AD4GD Project](https://www.ogc.org/initiatives/ad4gd/).
