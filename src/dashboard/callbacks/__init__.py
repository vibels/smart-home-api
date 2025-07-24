from src.models.sensor import TemperatureModel, HumidityModel, MotionModel, GasModel

temp_model = TemperatureModel()
humidity_model = HumidityModel()
motion_model = MotionModel()
gas_model = GasModel()
sensor_models = [temp_model, humidity_model, motion_model, gas_model]