from OMPython import OMCSession
import os

omc = OMCSession()

# Load Modelica Standard Library (assume installed with OpenModelica)
omc.sendExpression('loadModel(Modelica)')

# Directory to save FMUs
output_dir = 'msl_fmus'
os.makedirs(output_dir, exist_ok=True)

# Example models to export (for full MSL, extend this list or use recursive search)
models = [
    'Modelica.Mechanics.Rotational.Examples.First',
    'Modelica.Mechanics.Translational.Examples.Force',
    'Modelica.Thermal.HeatTransfer.Examples.SimpleRadiator',
    'Modelica.Blocks.Examples.PID_Controller',
    'Modelica.Electrical.Analog.Examples.Circuit1',
    # Add more, e.g., 'Modelica.Mechanics.MultiBody.Examples.Elementary.BouncingBall'
    'Modelica.Mechanics.MultiBody.Examples.Elementary.BouncingBall'
]

for model in models:
    try:
        # Export ME
        me_fmu = os.path.join(output_dir, f'{model.replace(".", "_")}_ME.fmu')
        omc.sendExpression(f'translateModelFMU({model}, version="3.0", fmuType="me", fileNamePrefix="{model.replace(".", "_")}_ME", outputFormat="csv", fmuTargetName="{me_fmu}")')
        
        # Export CS
        cs_fmu = os.path.join(output_dir, f'{model.replace(".", "_")}_CS.fmu')
        omc.sendExpression(f'translateModelFMU({model}, version="3.0", fmuType="cs", fileNamePrefix="{model.replace(".", "_")}_CS", outputFormat="csv", fmuTargetName="{cs_fmu}")')
        
        print(f'Exported {model} to ME and CS FMUs')
    except Exception as e:
        print(f'Failed to export {model}: {e}')

print('Export complete. For full MSL, extend the models list or use OpenModelica\'s library browser to identify all examples and components.')
