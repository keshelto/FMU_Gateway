model TurboSpoolUp
  "Simple turbocharger spool-up model for demonstration"
  
  // Parameters
  parameter Real J_turbo = 0.01 "Turbo inertia (kg⋅m²)";
  parameter Real J_engine = 0.1 "Engine inertia (kg⋅m²)";
  parameter Real k_turbo = 0.5 "Turbo damping coefficient";
  parameter Real k_engine = 2.0 "Engine damping coefficient";
  parameter Real gear_ratio = 1.0 "Gear ratio between engine and turbo";
  parameter Real boost_pressure_ratio = 2.0 "Target boost pressure ratio";
  parameter Real spool_time_constant = 0.5 "Spool-up time constant (s)";
  
  // Variables
  Real omega_turbo(start = 0) "Turbo angular velocity (rad/s)";
  Real omega_engine(start = 0) "Engine angular velocity (rad/s)";
  Real torque_turbo "Turbo torque (N⋅m)";
  Real torque_engine "Engine torque (N⋅m)";
  Real boost_pressure "Boost pressure (bar)";
  Real n_turbo "Turbo speed (rpm)";
  Real n_engine "Engine speed (rpm)";
  Real throttle_input "Throttle input (0-1)";
  
  // Input signals
  input Real throttle(start = 0) "Throttle position (0-1)";
  input Real engine_load(start = 0) "Engine load torque (N⋅m)";
  
equation
  // Convert throttle to smooth input
  der(throttle_input) = (throttle - throttle_input) / 0.1;
  
  // Engine dynamics
  J_engine * der(omega_engine) = torque_engine - k_engine * omega_engine - engine_load;
  
  // Turbo dynamics
  J_turbo * der(omega_turbo) = torque_turbo - k_turbo * omega_turbo;
  
  // Engine torque (simplified - increases with throttle and speed)
  torque_engine = 50 * throttle_input * (1 + 0.1 * omega_engine);
  
  // Turbo torque (simplified - driven by exhaust energy)
  torque_turbo = 20 * throttle_input * (1 + 0.05 * omega_engine) * (1 - omega_turbo / 1000);
  
  // Boost pressure calculation
  boost_pressure = 1.0 + (boost_pressure_ratio - 1.0) * (1 - exp(-omega_turbo / (spool_time_constant * 100)));
  
  // Convert to RPM
  n_turbo = omega_turbo * 60 / (2 * 3.14159);
  n_engine = omega_engine * 60 / (2 * 3.14159);
  
  // Output variables for analysis
  output Real turbo_speed = n_turbo;
  output Real engine_speed = n_engine;
  output Real boost = boost_pressure;
  output Real turbo_torque = torque_turbo;
  output Real engine_torque = torque_engine;

annotation(
  Documentation(info="<html>
  <p>Simple turbocharger spool-up model for demonstrating FMU Gateway capabilities.</p>
  <p>This model simulates:</p>
  <ul>
    <li>Turbo and engine rotational dynamics</li>
    <li>Boost pressure build-up</li>
    <li>Spool-up characteristics</li>
  </ul>
  <p>Inputs:</p>
  <ul>
    <li>throttle: Throttle position (0-1)</li>
    <li>engine_load: Engine load torque (N⋅m)</li>
  </ul>
  <p>Outputs:</p>
  <ul>
    <li>turbo_speed: Turbo speed (rpm)</li>
    <li>engine_speed: Engine speed (rpm)</li>
    <li>boost: Boost pressure (bar)</li>
    <li>turbo_torque: Turbo torque (N⋅m)</li>
    <li>engine_torque: Engine torque (N⋅m)</li>
  </ul>
  </html>"),
  Icon(graphics={
    Rectangle(extent={{-100,100},{100,-100}}, lineColor={0,0,0}),
    Text(extent={{-80,80},{80,-80}}, textString="Turbo\nSpool-Up", fontSize=16)
  })
);
end TurboSpoolUp;
