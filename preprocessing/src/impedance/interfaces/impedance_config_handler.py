from abc import ABC, abstractmethod

class ImpedanceConfigurationHandler(ABC):
    """Abstract class for processing impedance configuration files."""
    
    def __init__(self, config:dict, config_impedance:dict, params_placeholder:dict, impedance_stressors:dict, year:int, 
        current_dir:str, output_dir:str) -> None:
        """Initializes the ImpedanceConfigProcessor class.

        Args:
            config (dict): The configuration yaml file.
            config_impedance (dict): The impedance configuration yaml file.
            params_placeholder (dict): The dictionary template for the configuration YAML file (for each stressor).
            impedance_stressors (dict): The dictionary for stressors, mapping stressor raster path to YAML alias.
            year (int): The year for which the edge effect is calculated.
            current_dir (str): The parent directory
            output_dir (str): The output directory
        """
        super().__init__()
        self.config = config
        self.config_impedance = config_impedance
        self.params_placeholder = params_placeholder
        self.impedance_stressors = impedance_stressors
        self.year = year
        self.current_dir = current_dir
        self.output_dir = output_dir
        
    @abstractmethod
    def update_impedance_config(self, *args, **kwargs) -> tuple[dict,dict]:
        """Updates the impedance configuration file with stressors and default decay parameters.
        
        Returns:
            impedance_dictionaries (tuple): Tuple containing two dictionaries:
                - Impedance_stressors (dict) The dictionary of stressors, mapping stressor raster path to YAML alias.
                - Impedance_configuration (dict): The updated configuration file mapping stressors to default decay parameters.
        """
        ...
