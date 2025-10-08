#!/usr/bin/env python3
"""
Analysis script to evaluate FMU Gateway performance on Turbo Spool Up example.
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

def load_results():
    """Load all result files from the output directory."""
    output_dir = Path(__file__).parent / "output"
    
    # Load summary and metrics
    with open(output_dir / "summary.json") as f:
        summary = json.load(f)
    
    with open(output_dir / "metrics.json") as f:
        metrics = json.load(f)
    
    # Load timeseries data
    timeseries = pd.read_csv(output_dir / "timeseries.csv")
    
    return summary, metrics, timeseries

def analyze_simulation_quality(timeseries, metrics):
    """Analyze the quality of the simulation results."""
    print("=== SIMULATION QUALITY ANALYSIS ===")
    
    # Check data completeness
    total_points = len(timeseries)
    print(f"Total data points: {total_points}")
    
    # Check for missing data
    missing_data = timeseries.isnull().sum()
    if missing_data.any():
        print(f"Missing data detected: {missing_data[missing_data > 0].to_dict()}")
    else:
        print("[OK] No missing data")
    
    # Check time step consistency
    time_diffs = timeseries['time'].diff().dropna()
    expected_step = 0.004  # From the data
    step_variation = time_diffs.std()
    print(f"Time step variation: {step_variation:.6f} (expected: ~0.004)")
    
    if step_variation < 1e-6:
        print("[OK] Consistent time stepping")
    else:
        print("[WARNING] Time step variation detected")
    
    # Analyze signal characteristics
    h_signal = timeseries['h'].values
    v_signal = timeseries['v'].values
    
    print(f"\nHeight (h) signal:")
    print(f"  Initial value: {h_signal[0]:.6f}")
    print(f"  Final value: {h_signal[-1]:.6f}")
    print(f"  Range: {h_signal.min():.6f} to {h_signal.max():.6f}")
    
    print(f"\nVelocity (v) signal:")
    print(f"  Initial value: {v_signal[0]:.6f}")
    print(f"  Final value: {v_signal[-1]:.6f}")
    print(f"  Range: {v_signal.min():.6f} to {v_signal.max():.6f}")
    print(f"  Peak speed: {metrics['peak_speed']:.6f}")
    
    return {
        'total_points': total_points,
        'step_variation': step_variation,
        'h_range': (h_signal.min(), h_signal.max()),
        'v_range': (v_signal.min(), v_signal.max())
    }

def analyze_physics_correctness(timeseries):
    """Analyze if the physics simulation is correct."""
    print("\n=== PHYSICS CORRECTNESS ANALYSIS ===")
    
    h = timeseries['h'].values
    v = timeseries['v'].values
    t = timeseries['time'].values
    
    # Check energy conservation (for bouncing ball)
    g = 9.81  # gravity
    dt = np.diff(t)
    
    # Calculate kinetic and potential energy
    kinetic_energy = 0.5 * v**2
    potential_energy = g * h
    total_energy = kinetic_energy + potential_energy
    
    # Check if energy is conserved (should be constant)
    energy_variation = np.std(total_energy)
    energy_mean = np.mean(total_energy)
    energy_conservation_error = energy_variation / energy_mean if energy_mean > 0 else float('inf')
    
    print(f"Energy conservation analysis:")
    print(f"  Mean total energy: {energy_mean:.6f}")
    print(f"  Energy variation (std): {energy_variation:.6f}")
    print(f"  Relative error: {energy_conservation_error:.2%}")
    
    if energy_conservation_error < 0.01:  # 1% error threshold
        print("[OK] Good energy conservation")
    elif energy_conservation_error < 0.05:  # 5% error threshold
        print("[WARNING] Moderate energy conservation issues")
    else:
        print("[ERROR] Poor energy conservation")
    
    # Check for expected bouncing behavior
    # Look for velocity sign changes (bounces)
    velocity_sign_changes = np.sum(np.diff(np.sign(v)) != 0)
    print(f"\nBouncing behavior:")
    print(f"  Number of bounces detected: {velocity_sign_changes}")
    
    if velocity_sign_changes > 0:
        print("[OK] Bouncing behavior detected")
    else:
        print("[WARNING] No bouncing detected - may be incorrect physics")
    
    # Check if ball eventually settles (height approaches zero)
    final_height = h[-1]
    if abs(final_height) < 0.01:
        print("[OK] Ball appears to have settled")
    else:
        print(f"[WARNING] Ball did not settle (final height: {final_height:.6f})")
    
    return {
        'energy_conservation_error': energy_conservation_error,
        'bounces_detected': velocity_sign_changes,
        'final_height': final_height
    }

def analyze_gateway_performance(summary, metrics):
    """Analyze FMU Gateway performance metrics."""
    print("\n=== FMU GATEWAY PERFORMANCE ===")
    
    # Check gateway status
    status = summary.get('status', 'unknown')
    print(f"Gateway status: {status}")
    
    if status == 'ok':
        print("[OK] Simulation completed successfully")
    else:
        print(f"[ERROR] Simulation failed with status: {status}")
    
    # Check provenance information
    provenance = summary.get('provenance', {})
    print(f"\nFMU Information:")
    print(f"  FMI Version: {provenance.get('fmi_version', 'unknown')}")
    print(f"  GUID: {provenance.get('guid', 'unknown')}")
    print(f"  SHA256: {provenance.get('sha256', 'unknown')[:16]}...")
    
    # Analyze computed metrics
    print(f"\nComputed Metrics:")
    for key, value in metrics.items():
        if value is not None:
            print(f"  {key}: {value:.6f}")
        else:
            print(f"  {key}: Not available")
    
    # Evaluate metric quality
    spool_time = metrics.get('spool_time_95')
    if spool_time is not None:
        if 0.1 < spool_time < 1.0:  # Reasonable range for bouncing ball
            print("[OK] Spool time within reasonable range")
        else:
            print(f"[WARNING] Spool time may be unrealistic: {spool_time:.6f}")
    
    return {
        'status': status,
        'fmi_version': provenance.get('fmi_version'),
        'metrics_available': sum(1 for v in metrics.values() if v is not None)
    }

def create_visualizations(timeseries, metrics, output_dir):
    """Create comprehensive visualizations of the results."""
    print("\n=== CREATING VISUALIZATIONS ===")
    
    # Set up the plotting style
    plt.style.use('default')
    fig = plt.figure(figsize=(15, 12))
    
    # Plot 1: Time series of height and velocity
    ax1 = plt.subplot(3, 2, 1)
    ax1.plot(timeseries['time'], timeseries['h'], 'b-', label='Height (h)', linewidth=2)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Height (m)')
    ax1.set_title('Ball Height vs Time')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    ax2 = plt.subplot(3, 2, 2)
    ax2.plot(timeseries['time'], timeseries['v'], 'r-', label='Velocity (v)', linewidth=2)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Velocity (m/s)')
    ax2.set_title('Ball Velocity vs Time')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    # Plot 2: Phase space (velocity vs height)
    ax3 = plt.subplot(3, 2, 3)
    ax3.plot(timeseries['h'], timeseries['v'], 'g-', linewidth=2)
    ax3.set_xlabel('Height (m)')
    ax3.set_ylabel('Velocity (m/s)')
    ax3.set_title('Phase Space (Velocity vs Height)')
    ax3.grid(True, alpha=0.3)
    
    # Plot 3: Energy analysis
    ax4 = plt.subplot(3, 2, 4)
    g = 9.81
    kinetic_energy = 0.5 * timeseries['v']**2
    potential_energy = g * timeseries['h']
    total_energy = kinetic_energy + potential_energy
    
    ax4.plot(timeseries['time'], kinetic_energy, 'b-', label='Kinetic Energy', alpha=0.7)
    ax4.plot(timeseries['time'], potential_energy, 'r-', label='Potential Energy', alpha=0.7)
    ax4.plot(timeseries['time'], total_energy, 'k-', label='Total Energy', linewidth=2)
    ax4.set_xlabel('Time (s)')
    ax4.set_ylabel('Energy (J/kg)')
    ax4.set_title('Energy Conservation Analysis')
    ax4.grid(True, alpha=0.3)
    ax4.legend()
    
    # Plot 4: Metrics summary
    ax5 = plt.subplot(3, 2, 5)
    metric_names = list(metrics.keys())
    metric_values = [v if v is not None else 0 for v in metrics.values()]
    colors = ['green' if v is not None else 'red' for v in metrics.values()]
    
    bars = ax5.bar(range(len(metric_names)), metric_values, color=colors, alpha=0.7)
    ax5.set_xlabel('Metrics')
    ax5.set_ylabel('Values')
    ax5.set_title('Computed Metrics Summary')
    ax5.set_xticks(range(len(metric_names)))
    ax5.set_xticklabels(metric_names, rotation=45, ha='right')
    ax5.grid(True, alpha=0.3)
    
    # Add value labels on bars
    for bar, value in zip(bars, metric_values):
        if value > 0:
            ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                    f'{value:.3f}', ha='center', va='bottom', fontsize=9)
    
    # Plot 5: Zoomed view of first bounce
    ax6 = plt.subplot(3, 2, 6)
    # Find first bounce (velocity sign change)
    v = timeseries['v'].values
    sign_changes = np.where(np.diff(np.sign(v)) != 0)[0]
    
    if len(sign_changes) > 0:
        first_bounce_idx = sign_changes[0]
        # Show data around first bounce
        start_idx = max(0, first_bounce_idx - 50)
        end_idx = min(len(timeseries), first_bounce_idx + 100)
        
        subset = timeseries.iloc[start_idx:end_idx]
        ax6.plot(subset['time'], subset['h'], 'b-', label='Height', linewidth=2)
        ax6_twin = ax6.twinx()
        ax6_twin.plot(subset['time'], subset['v'], 'r-', label='Velocity', linewidth=2)
        
        ax6.set_xlabel('Time (s)')
        ax6.set_ylabel('Height (m)', color='b')
        ax6_twin.set_ylabel('Velocity (m/s)', color='r')
        ax6.set_title('First Bounce Detail')
        ax6.grid(True, alpha=0.3)
        
        # Mark the bounce point
        bounce_time = subset['time'].iloc[first_bounce_idx - start_idx]
        ax6.axvline(bounce_time, color='k', linestyle='--', alpha=0.7, label='Bounce')
        ax6.legend(loc='upper left')
        ax6_twin.legend(loc='upper right')
    else:
        ax6.text(0.5, 0.5, 'No bounces detected', ha='center', va='center', 
                transform=ax6.transAxes, fontsize=12)
        ax6.set_title('First Bounce Detail')
    
    plt.tight_layout()
    
    # Save the plot
    plot_path = output_dir / "analysis_plots.png"
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    print(f"[OK] Visualization saved to: {plot_path}")
    
    return plot_path

def generate_assessment_report(summary, metrics, timeseries, quality_analysis, physics_analysis, performance_analysis):
    """Generate a comprehensive assessment report."""
    print("\n" + "="*60)
    print("FMU GATEWAY PERFORMANCE ASSESSMENT REPORT")
    print("="*60)
    
    # Overall assessment
    print("\nOVERALL ASSESSMENT:")
    
    issues = []
    successes = []
    
    # Check simulation completion
    if performance_analysis['status'] == 'ok':
        successes.append("[OK] Simulation completed successfully")
    else:
        issues.append(f"[ERROR] Simulation failed: {performance_analysis['status']}")
    
    # Check data quality
    if quality_analysis['step_variation'] < 1e-6:
        successes.append("[OK] Consistent time stepping")
    else:
        issues.append("[WARNING] Time step variation detected")
    
    # Check physics
    if physics_analysis['energy_conservation_error'] < 0.05:
        successes.append("[OK] Good energy conservation")
    else:
        issues.append("[ERROR] Poor energy conservation")
    
    if physics_analysis['bounces_detected'] > 0:
        successes.append("[OK] Bouncing behavior detected")
    else:
        issues.append("[WARNING] No bouncing behavior detected")
    
    # Check metrics computation
    if performance_analysis['metrics_available'] >= 2:
        successes.append("[OK] Key metrics computed successfully")
    else:
        issues.append("[WARNING] Limited metrics available")
    
    print("\nSUCCESSES:")
    for success in successes:
        print(f"  {success}")
    
    if issues:
        print("\nISSUES:")
        for issue in issues:
            print(f"  {issue}")
    
    # Performance score
    total_checks = len(successes) + len(issues)
    success_rate = len(successes) / total_checks * 100
    
    print(f"\nPERFORMANCE SCORE: {success_rate:.1f}% ({len(successes)}/{total_checks} checks passed)")
    
    if success_rate >= 80:
        print("VERDICT: EXCELLENT - FMU Gateway performed very well")
    elif success_rate >= 60:
        print("VERDICT: GOOD - FMU Gateway performed adequately with minor issues")
    elif success_rate >= 40:
        print("VERDICT: FAIR - FMU Gateway had some issues but completed basic functionality")
    else:
        print("VERDICT: POOR - FMU Gateway had significant issues")
    
    # Detailed findings
    print(f"\nDETAILED FINDINGS:")
    print(f"  • Simulation completed with {quality_analysis['total_points']} data points")
    print(f"  • Energy conservation error: {physics_analysis['energy_conservation_error']:.2%}")
    print(f"  • Number of bounces detected: {physics_analysis['bounces_detected']}")
    print(f"  • Final ball height: {physics_analysis['final_height']:.6f} m")
    print(f"  • Metrics computed: {performance_analysis['metrics_available']}/4")
    
    if metrics.get('spool_time_95'):
        print(f"  • 95% spool time: {metrics['spool_time_95']:.3f} s")
    
    return {
        'success_rate': success_rate,
        'issues': issues,
        'successes': successes,
        'verdict': 'EXCELLENT' if success_rate >= 80 else 'GOOD' if success_rate >= 60 else 'FAIR' if success_rate >= 40 else 'POOR'
    }

def main():
    """Main analysis function."""
    print("FMU Gateway Turbo Spool Up Analysis")
    print("="*40)
    
    # Load results
    summary, metrics, timeseries = load_results()
    
    # Perform analyses
    quality_analysis = analyze_simulation_quality(timeseries, metrics)
    physics_analysis = analyze_physics_correctness(timeseries)
    performance_analysis = analyze_gateway_performance(summary, metrics)
    
    # Create visualizations
    output_dir = Path(__file__).parent / "output"
    plot_path = create_visualizations(timeseries, metrics, output_dir)
    
    # Generate assessment report
    assessment = generate_assessment_report(
        summary, metrics, timeseries, 
        quality_analysis, physics_analysis, performance_analysis
    )
    
    # Save assessment to file
    assessment_path = output_dir / "assessment_report.json"
    
    # Convert numpy types to Python types for JSON serialization
    def convert_numpy_types(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj
    
    assessment_data = {
        'assessment': assessment,
        'quality_analysis': {k: convert_numpy_types(v) for k, v in quality_analysis.items()},
        'physics_analysis': {k: convert_numpy_types(v) for k, v in physics_analysis.items()},
        'performance_analysis': performance_analysis,
        'metrics': metrics,
        'summary': summary
    }
    
    with open(assessment_path, 'w') as f:
        json.dump(assessment_data, f, indent=2)
    
    print(f"\n[OK] Assessment report saved to: {assessment_path}")
    print(f"[OK] Analysis complete!")

if __name__ == "__main__":
    main()
