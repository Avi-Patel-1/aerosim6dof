"""Mission-control style metadata for simulator telemetry channels."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

TelemetrySource = Literal["history", "truth", "controls", "sensors", "derived"]
TelemetryRole = Literal[
    "truth",
    "sensor",
    "command",
    "actuator_state",
    "environment",
    "aero",
    "gnc",
    "propulsion",
    "derived",
]


@dataclass(frozen=True)
class TelemetryRange:
    min: float | None = None
    max: float | None = None
    label: str = ""


@dataclass(frozen=True)
class TelemetryChannelMetadata:
    key: str
    display_name: str
    unit: str = ""
    description: str = ""
    group: str = "Unknown"
    source: TelemetrySource = "history"
    role: TelemetryRole = "truth"
    valid_range: TelemetryRange | None = None
    caution_range: TelemetryRange | None = None
    warning_range: TelemetryRange | None = None
    fatal_range: TelemetryRange | None = None
    sample_rate_hz: float | None = None
    derived: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def metadata_for_channels(channels: dict[str, list[str]]) -> dict[str, dict[str, object]]:
    """Return known metadata plus safe fallbacks for a telemetry channel map."""
    result: dict[str, dict[str, object]] = {}
    detected_sources = _detected_sources(channels)
    for key in sorted(detected_sources):
        metadata = KNOWN_CHANNELS.get(key) or _fallback_metadata(key, detected_sources[key])
        result[key] = metadata.to_dict()
    return result


def _m(
    key: str,
    display_name: str,
    unit: str = "",
    description: str = "",
    group: str = "Unknown",
    source: TelemetrySource = "history",
    role: TelemetryRole = "truth",
    valid_range: TelemetryRange | None = None,
    caution_range: TelemetryRange | None = None,
    warning_range: TelemetryRange | None = None,
    fatal_range: TelemetryRange | None = None,
    sample_rate_hz: float | None = None,
    derived: bool = False,
) -> TelemetryChannelMetadata:
    return TelemetryChannelMetadata(
        key=key,
        display_name=display_name,
        unit=unit,
        description=description,
        group=group,
        source=source,
        role=role,
        valid_range=valid_range,
        caution_range=caution_range,
        warning_range=warning_range,
        fatal_range=fatal_range,
        sample_rate_hz=sample_rate_hz,
        derived=derived,
    )


def _r(minimum: float | None = None, maximum: float | None = None, label: str = "") -> TelemetryRange:
    return TelemetryRange(min=minimum, max=maximum, label=label)


KNOWN_CHANNELS: dict[str, TelemetryChannelMetadata] = {
    "time_s": _m("time_s", "Mission Elapsed Time", "s", "Simulation time from run start.", "Timing"),
    "sensor_time_s": _m("sensor_time_s", "Sensor Sample Time", "s", "Timestamp attached to sampled sensor outputs.", "Timing", "sensors", "sensor"),
    "x_m": _m("x_m", "Downrange Position", "m", "Vehicle inertial x position in the scenario frame.", "State", "truth", "truth"),
    "y_m": _m("y_m", "Crossrange Position", "m", "Vehicle inertial y position in the scenario frame.", "State", "truth", "truth"),
    "altitude_m": _m(
        "altitude_m",
        "Altitude",
        "m",
        "Vehicle altitude above the inertial reference plane.",
        "State",
        "truth",
        "truth",
        valid_range=_r(-1000.0, None, "valid"),
        caution_range=_r(0.0, None, "above ground reference"),
    ),
    "terrain_elevation_m": _m(
        "terrain_elevation_m",
        "Terrain Elevation",
        "m",
        "Terrain height at the vehicle ground-projected position.",
        "Environment",
        "truth",
        "environment",
    ),
    "altitude_agl_m": _m("altitude_agl_m", "Altitude AGL", "m", "Height above the active terrain model.", "State", "truth", "truth", valid_range=_r(0.0, None)),
    "vx_mps": _m("vx_mps", "Velocity X", "m/s", "Vehicle velocity along the scenario x axis.", "State", "truth", "truth"),
    "vy_mps": _m("vy_mps", "Velocity Y", "m/s", "Vehicle velocity along the scenario y axis.", "State", "truth", "truth"),
    "vz_mps": _m("vz_mps", "Vertical Velocity", "m/s", "Vehicle vertical velocity.", "State", "truth", "truth"),
    "speed_mps": _m("speed_mps", "Speed", "m/s", "Magnitude of vehicle velocity.", "State", "truth", "truth", valid_range=_r(0.0, None)),
    "mass_kg": _m("mass_kg", "Vehicle Mass", "kg", "Current vehicle mass after propellant use.", "Mass", "truth", "truth", valid_range=_r(0.0, None)),
    "roll_deg": _m("roll_deg", "Roll", "deg", "Vehicle roll Euler angle.", "Attitude", "truth", "truth", valid_range=_r(-180.0, 180.0)),
    "pitch_deg": _m("pitch_deg", "Pitch", "deg", "Vehicle pitch Euler angle.", "Attitude", "truth", "truth", valid_range=_r(-180.0, 180.0)),
    "yaw_deg": _m("yaw_deg", "Yaw", "deg", "Vehicle yaw Euler angle.", "Attitude", "truth", "truth", valid_range=_r(-180.0, 180.0)),
    "p_dps": _m("p_dps", "Roll Rate", "deg/s", "Body-axis roll rate.", "Rates", "truth", "truth"),
    "q_dps": _m("q_dps", "Pitch Rate", "deg/s", "Body-axis pitch rate.", "Rates", "truth", "truth"),
    "r_dps": _m("r_dps", "Yaw Rate", "deg/s", "Body-axis yaw rate.", "Rates", "truth", "truth"),
    "alpha_deg": _m("alpha_deg", "Angle of Attack", "deg", "Aerodynamic angle of attack.", "Aerodynamics", "history", "aero", warning_range=_r(-20.0, 20.0, "nominal envelope")),
    "beta_deg": _m("beta_deg", "Sideslip", "deg", "Aerodynamic sideslip angle.", "Aerodynamics", "history", "aero", warning_range=_r(-20.0, 20.0, "nominal envelope")),
    "qbar_pa": _m(
        "qbar_pa",
        "Dynamic Pressure",
        "Pa",
        "Freestream dynamic pressure used by aerodynamic force calculations.",
        "Aerodynamics",
        "history",
        "aero",
        valid_range=_r(0.0, None),
        caution_range=_r(None, 40000.0, "caution ceiling"),
        warning_range=_r(None, 60000.0, "warning ceiling"),
    ),
    "mach": _m("mach", "Mach", "", "Freestream Mach number.", "Aerodynamics", "history", "aero", valid_range=_r(0.0, None)),
    "airspeed_mps": _m("airspeed_mps", "Airspeed", "m/s", "Vehicle speed relative to the local wind.", "Aerodynamics", "history", "aero", valid_range=_r(0.0, None)),
    "load_factor_g": _m(
        "load_factor_g",
        "Load Factor",
        "g",
        "Estimated acceleration load factor.",
        "Aerodynamics",
        "history",
        "aero",
        caution_range=_r(None, 4.0, "caution ceiling"),
        warning_range=_r(None, 6.0, "warning ceiling"),
    ),
    "density_kgpm3": _m("density_kgpm3", "Air Density", "kg/m^3", "Atmospheric density at vehicle altitude.", "Environment", "history", "environment", valid_range=_r(0.0, None)),
    "pressure_pa": _m("pressure_pa", "Static Pressure", "Pa", "Atmospheric static pressure at vehicle altitude.", "Environment", "history", "environment", valid_range=_r(0.0, None)),
    "temperature_k": _m("temperature_k", "Temperature", "K", "Atmospheric temperature at vehicle altitude.", "Environment", "history", "environment", valid_range=_r(0.0, None)),
    "wind_x_mps": _m("wind_x_mps", "Wind X", "m/s", "Local wind along the scenario x axis.", "Environment", "history", "environment"),
    "wind_y_mps": _m("wind_y_mps", "Wind Y", "m/s", "Local wind along the scenario y axis.", "Environment", "history", "environment"),
    "wind_z_mps": _m("wind_z_mps", "Wind Z", "m/s", "Local vertical wind.", "Environment", "history", "environment"),
    "thrust_n": _m("thrust_n", "Thrust", "N", "Current propulsion thrust.", "Propulsion", "history", "propulsion", valid_range=_r(0.0, None)),
    "mass_flow_kgps": _m("mass_flow_kgps", "Mass Flow", "kg/s", "Propellant mass flow rate.", "Propulsion", "history", "propulsion", valid_range=_r(0.0, None)),
    "propulsion_throttle_actual": _m("propulsion_throttle_actual", "Actual Throttle", "", "Propulsion throttle after actuator and health effects.", "Propulsion", "history", "propulsion", valid_range=_r(0.0, 1.0)),
    "propulsion_health": _m("propulsion_health", "Propulsion Health", "", "Propulsion health multiplier used by the engine model.", "Propulsion", "history", "propulsion", valid_range=_r(0.0, 1.0)),
    "energy_j_per_kg": _m("energy_j_per_kg", "Specific Energy", "J/kg", "Specific mechanical energy proxy.", "Derived", "derived", "derived", derived=True),
    "target_distance_m": _m("target_distance_m", "Target Distance", "m", "Distance from vehicle to active guidance target.", "GNC", "history", "gnc", valid_range=_r(0.0, None)),
    "guidance_mode": _m("guidance_mode", "Guidance Mode", "", "Active guidance mode name.", "GNC", "history", "gnc"),
    "pitch_command_deg": _m("pitch_command_deg", "Pitch Command", "deg", "Pitch angle command from guidance.", "GNC", "history", "command"),
    "heading_command_deg": _m("heading_command_deg", "Heading Command", "deg", "Heading command from guidance.", "GNC", "history", "command"),
    "roll_command_deg": _m("roll_command_deg", "Roll Command", "deg", "Roll angle command from guidance.", "GNC", "history", "command"),
    "elevator_command_deg": _m("elevator_command_deg", "Elevator Command", "deg", "Commanded elevator deflection before actuator response.", "Controls", "controls", "command"),
    "aileron_command_deg": _m("aileron_command_deg", "Aileron Command", "deg", "Commanded aileron deflection before actuator response.", "Controls", "controls", "command"),
    "rudder_command_deg": _m("rudder_command_deg", "Rudder Command", "deg", "Commanded rudder deflection before actuator response.", "Controls", "controls", "command"),
    "elevator_deg": _m("elevator_deg", "Elevator", "deg", "Actual elevator deflection after actuator dynamics and failures.", "Actuators", "controls", "actuator_state", valid_range=_r(-45.0, 45.0)),
    "aileron_deg": _m("aileron_deg", "Aileron", "deg", "Actual aileron deflection after actuator dynamics and failures.", "Actuators", "controls", "actuator_state", valid_range=_r(-45.0, 45.0)),
    "rudder_deg": _m("rudder_deg", "Rudder", "deg", "Actual rudder deflection after actuator dynamics and failures.", "Actuators", "controls", "actuator_state", valid_range=_r(-45.0, 45.0)),
    "throttle": _m("throttle", "Throttle Command", "", "Commanded throttle sent to the propulsion model.", "Controls", "controls", "command", valid_range=_r(0.0, 1.0)),
    "elevator_saturated": _m("elevator_saturated", "Elevator Saturated", "", "Boolean flag showing elevator limit or rate saturation.", "Actuators", "controls", "actuator_state", valid_range=_r(0.0, 1.0)),
    "aileron_saturated": _m("aileron_saturated", "Aileron Saturated", "", "Boolean flag showing aileron limit or rate saturation.", "Actuators", "controls", "actuator_state", valid_range=_r(0.0, 1.0)),
    "rudder_saturated": _m("rudder_saturated", "Rudder Saturated", "", "Boolean flag showing rudder limit or rate saturation.", "Actuators", "controls", "actuator_state", valid_range=_r(0.0, 1.0)),
    "elevator_failed": _m("elevator_failed", "Elevator Failed", "", "Boolean flag showing elevator failure state.", "Actuators", "controls", "actuator_state", valid_range=_r(0.0, 1.0)),
    "aileron_failed": _m("aileron_failed", "Aileron Failed", "", "Boolean flag showing aileron failure state.", "Actuators", "controls", "actuator_state", valid_range=_r(0.0, 1.0)),
    "rudder_failed": _m("rudder_failed", "Rudder Failed", "", "Boolean flag showing rudder failure state.", "Actuators", "controls", "actuator_state", valid_range=_r(0.0, 1.0)),
    "elevator_raw_rad": _m("elevator_raw_rad", "Elevator Raw", "rad", "Raw elevator command inside actuator model.", "Actuators", "controls", "command"),
    "aileron_raw_rad": _m("aileron_raw_rad", "Aileron Raw", "rad", "Raw aileron command inside actuator model.", "Actuators", "controls", "command"),
    "rudder_raw_rad": _m("rudder_raw_rad", "Rudder Raw", "rad", "Raw rudder command inside actuator model.", "Actuators", "controls", "command"),
    "elevator_effective_rad": _m("elevator_effective_rad", "Elevator Effective", "rad", "Effective elevator deflection used by the vehicle model.", "Actuators", "controls", "actuator_state"),
    "aileron_effective_rad": _m("aileron_effective_rad", "Aileron Effective", "rad", "Effective aileron deflection used by the vehicle model.", "Actuators", "controls", "actuator_state"),
    "rudder_effective_rad": _m("rudder_effective_rad", "Rudder Effective", "rad", "Effective rudder deflection used by the vehicle model.", "Actuators", "controls", "actuator_state"),
    "imu_valid": _m("imu_valid", "IMU Valid", "", "IMU sample validity flag.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, 1.0)),
    "imu_ax_mps2": _m("imu_ax_mps2", "IMU Accel X", "m/s^2", "IMU measured acceleration along body x.", "Sensors", "sensors", "sensor"),
    "imu_ay_mps2": _m("imu_ay_mps2", "IMU Accel Y", "m/s^2", "IMU measured acceleration along body y.", "Sensors", "sensors", "sensor"),
    "imu_az_mps2": _m("imu_az_mps2", "IMU Accel Z", "m/s^2", "IMU measured acceleration along body z.", "Sensors", "sensors", "sensor"),
    "gyro_p_rps": _m("gyro_p_rps", "Gyro Roll Rate", "rad/s", "Gyroscope roll-rate measurement.", "Sensors", "sensors", "sensor"),
    "gyro_q_rps": _m("gyro_q_rps", "Gyro Pitch Rate", "rad/s", "Gyroscope pitch-rate measurement.", "Sensors", "sensors", "sensor"),
    "gyro_r_rps": _m("gyro_r_rps", "Gyro Yaw Rate", "rad/s", "Gyroscope yaw-rate measurement.", "Sensors", "sensors", "sensor"),
    "imu_accel_norm_mps2": _m("imu_accel_norm_mps2", "IMU Accel Norm", "m/s^2", "Magnitude of IMU acceleration measurement.", "Sensors", "sensors", "sensor", derived=True),
    "imu_gyro_norm_rps": _m("imu_gyro_norm_rps", "IMU Gyro Norm", "rad/s", "Magnitude of gyroscope rate measurement.", "Sensors", "sensors", "sensor", derived=True),
    "gps_valid": _m("gps_valid", "GPS Valid", "", "GPS sample validity flag.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, 1.0)),
    "gps_latency_s": _m("gps_latency_s", "GPS Latency", "s", "Latency applied to the GPS sample.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, None)),
    "gps_x_m": _m("gps_x_m", "GPS X", "m", "GPS measured x position.", "Sensors", "sensors", "sensor"),
    "gps_y_m": _m("gps_y_m", "GPS Y", "m", "GPS measured y position.", "Sensors", "sensors", "sensor"),
    "gps_z_m": _m("gps_z_m", "GPS Altitude", "m", "GPS measured altitude.", "Sensors", "sensors", "sensor"),
    "gps_vx_mps": _m("gps_vx_mps", "GPS Velocity X", "m/s", "GPS measured x velocity.", "Sensors", "sensors", "sensor"),
    "gps_vy_mps": _m("gps_vy_mps", "GPS Velocity Y", "m/s", "GPS measured y velocity.", "Sensors", "sensors", "sensor"),
    "gps_vz_mps": _m("gps_vz_mps", "GPS Vertical Velocity", "m/s", "GPS measured vertical velocity.", "Sensors", "sensors", "sensor"),
    "baro_valid": _m("baro_valid", "Barometer Valid", "", "Barometer sample validity flag.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, 1.0)),
    "baro_alt_m": _m("baro_alt_m", "Barometer Altitude", "m", "Barometric altitude estimate.", "Sensors", "sensors", "sensor"),
    "baro_bias_m": _m("baro_bias_m", "Barometer Bias", "m", "Modeled barometric altitude bias.", "Sensors", "sensors", "sensor"),
    "pitot_valid": _m("pitot_valid", "Pitot Valid", "", "Pitot sample validity flag.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, 1.0)),
    "pitot_airspeed_mps": _m("pitot_airspeed_mps", "Pitot Airspeed", "m/s", "Pitot-derived airspeed measurement.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, None)),
    "pitot_qbar_pa": _m("pitot_qbar_pa", "Pitot Dynamic Pressure", "Pa", "Pitot-derived dynamic pressure measurement.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, None)),
    "pitot_compressibility_factor": _m("pitot_compressibility_factor", "Pitot Compressibility", "", "Pitot compressibility correction factor.", "Sensors", "sensors", "sensor"),
    "mag_valid": _m("mag_valid", "Magnetometer Valid", "", "Magnetometer sample validity flag.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, 1.0)),
    "mag_heading_deg": _m("mag_heading_deg", "Magnetic Heading", "deg", "Magnetometer-derived heading estimate.", "Sensors", "sensors", "sensor"),
    "mag_x_ut": _m("mag_x_ut", "Magnetic Field X", "uT", "Magnetometer x-axis field measurement.", "Sensors", "sensors", "sensor"),
    "mag_y_ut": _m("mag_y_ut", "Magnetic Field Y", "uT", "Magnetometer y-axis field measurement.", "Sensors", "sensors", "sensor"),
    "mag_z_ut": _m("mag_z_ut", "Magnetic Field Z", "uT", "Magnetometer z-axis field measurement.", "Sensors", "sensors", "sensor"),
    "radar_valid": _m("radar_valid", "Radar Altimeter Valid", "", "Radar altimeter sample validity flag.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, 1.0)),
    "radar_agl_m": _m("radar_agl_m", "Radar Altitude AGL", "m", "Radar altimeter range-to-ground measurement.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, None)),
    "optical_flow_valid": _m("optical_flow_valid", "Optical Flow Valid", "", "Optical-flow sample validity flag.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, 1.0)),
    "optical_flow_x_radps": _m("optical_flow_x_radps", "Optical Flow X", "rad/s", "Optical-flow angular rate about image x.", "Sensors", "sensors", "sensor"),
    "optical_flow_y_radps": _m("optical_flow_y_radps", "Optical Flow Y", "rad/s", "Optical-flow angular rate about image y.", "Sensors", "sensors", "sensor"),
    "optical_flow_quality": _m("optical_flow_quality", "Optical Flow Quality", "", "Optical-flow quality indicator.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, 1.0)),
    "horizon_valid": _m("horizon_valid", "Horizon Sensor Valid", "", "Horizon sensor validity flag.", "Sensors", "sensors", "sensor", valid_range=_r(0.0, 1.0)),
    "horizon_roll_deg": _m("horizon_roll_deg", "Horizon Roll", "deg", "Horizon sensor roll estimate.", "Sensors", "sensors", "sensor"),
    "horizon_pitch_deg": _m("horizon_pitch_deg", "Horizon Pitch", "deg", "Horizon sensor pitch estimate.", "Sensors", "sensors", "sensor"),
}

_SOURCE_PRIORITY: tuple[TelemetrySource, ...] = ("controls", "sensors", "truth", "history")


def _detected_sources(channels: dict[str, list[str]]) -> dict[str, TelemetrySource]:
    detected: dict[str, TelemetrySource] = {}
    for source in _SOURCE_PRIORITY:
        for key in channels.get(source, []):
            detected.setdefault(key, source)
    for source, keys in channels.items():
        normalized_source = source if source in {"history", "truth", "controls", "sensors"} else "history"
        for key in keys:
            detected.setdefault(key, normalized_source)  # type: ignore[arg-type]
    return detected


def _fallback_metadata(key: str, source: TelemetrySource) -> TelemetryChannelMetadata:
    return TelemetryChannelMetadata(
        key=key,
        display_name=_display_name(key),
        unit=_infer_unit(key),
        description="Telemetry channel discovered from run output.",
        group="Unknown",
        source=source,
        role=_infer_role(source, key),
        derived=False,
    )


def _display_name(key: str) -> str:
    acronyms = {"imu": "IMU", "gps": "GPS", "agl": "AGL", "qbar": "Qbar"}
    unit_suffixes = ("kgpm3", "j", "per", "kg", "mps2", "radps", "kgps", "mps", "dps", "rps", "deg", "pa", "ut", "hz", "k", "n", "s", "m", "g")
    parts = key.split("_")
    while parts and parts[-1].lower() in unit_suffixes:
        parts.pop()
    words = []
    for part in parts or [key]:
        words.append(acronyms.get(part.lower(), part.capitalize()))
    return " ".join(words)


def _infer_unit(key: str) -> str:
    suffix_units = (
        ("_kgpm3", "kg/m^3"),
        ("_j_per_kg", "J/kg"),
        ("_mps2", "m/s^2"),
        ("_radps", "rad/s"),
        ("_kgps", "kg/s"),
        ("_mps", "m/s"),
        ("_dps", "deg/s"),
        ("_rps", "rad/s"),
        ("_deg", "deg"),
        ("_pa", "Pa"),
        ("_kg", "kg"),
        ("_ut", "uT"),
        ("_hz", "Hz"),
        ("_k", "K"),
        ("_n", "N"),
        ("_s", "s"),
        ("_m", "m"),
        ("_g", "g"),
    )
    for suffix, unit in suffix_units:
        if key.endswith(suffix):
            return unit
    return ""


def _infer_role(source: TelemetrySource, key: str) -> TelemetryRole:
    if key.endswith("_command_deg") or key == "throttle":
        return "command"
    if "saturated" in key or "failed" in key or key.endswith("_deg"):
        return "actuator_state" if source == "controls" else "truth"
    if source == "sensors":
        return "sensor"
    if source == "controls":
        return "actuator_state"
    return "truth"
