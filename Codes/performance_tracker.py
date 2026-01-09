#!/usr/bin/env python3
"""
Performance Comparison Tool
===========================

Compare processing times between original and optimized methods.
Run this during/after processing to track improvements.

Usage:
    python performance_tracker.py start step_7
    python performance_tracker.py end step_7
    python performance_tracker.py report
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta
import sys


class PerformanceTracker:
    """Track and compare processing performance."""
    
    def __init__(self, log_file='performance_log.json'):
        self.log_file = Path(log_file)
        self.data = self.load_log()
    
    def load_log(self):
        """Load existing log or create new."""
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                return json.load(f)
        return {
            'runs': [],
            'steps': {}
        }
    
    def save_log(self):
        """Save log to file."""
        with open(self.log_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def start_step(self, step_name, method='optimized'):
        """Start timing a step."""
        if step_name not in self.data['steps']:
            self.data['steps'][step_name] = []
        
        entry = {
            'method': method,
            'start_time': time.time(),
            'start_datetime': datetime.now().isoformat(),
            'end_time': None,
            'duration': None
        }
        
        self.data['steps'][step_name].append(entry)
        self.save_log()
        
        print(f"⏱️  Started timing: {step_name} ({method})")
        print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
    
    def end_step(self, step_name):
        """End timing a step."""
        if step_name not in self.data['steps']:
            print(f"❌ No start time found for {step_name}")
            return
        
        # Find most recent entry without end_time
        for entry in reversed(self.data['steps'][step_name]):
            if entry['end_time'] is None:
                entry['end_time'] = time.time()
                entry['duration'] = entry['end_time'] - entry['start_time']
                self.save_log()
                
                print(f"✅ Completed: {step_name}")
                print(f"   Duration: {timedelta(seconds=int(entry['duration']))}")
                print(f"   Method: {entry['method']}")
                return
        
        print(f"⚠️  No active timing found for {step_name}")
    
    def get_comparison(self, step_name):
        """Get comparison between methods for a step."""
        if step_name not in self.data['steps']:
            return None
        
        entries = self.data['steps'][step_name]
        completed = [e for e in entries if e['duration'] is not None]
        
        if not completed:
            return None
        
        # Group by method
        by_method = {}
        for entry in completed:
            method = entry['method']
            if method not in by_method:
                by_method[method] = []
            by_method[method].append(entry['duration'])
        
        # Calculate averages
        comparison = {}
        for method, durations in by_method.items():
            comparison[method] = {
                'count': len(durations),
                'avg_seconds': sum(durations) / len(durations),
                'min_seconds': min(durations),
                'max_seconds': max(durations),
                'total_seconds': sum(durations)
            }
        
        return comparison
    
    def print_report(self):
        """Print comprehensive report."""
        print("\n" + "="*70)
        print("PERFORMANCE REPORT")
        print("="*70)
        
        if not self.data['steps']:
            print("\nNo timing data available yet.")
            print("Start tracking with: python performance_tracker.py start step_name")
            return
        
        for step_name in sorted(self.data['steps'].keys()):
            comparison = self.get_comparison(step_name)
            if not comparison:
                continue
            
            print(f"\n{step_name}")
            print("-" * 70)
            
            for method, stats in comparison.items():
                avg_time = timedelta(seconds=int(stats['avg_seconds']))
                total_time = timedelta(seconds=int(stats['total_seconds']))
                
                print(f"  {method.upper()}:")
                print(f"    Runs: {stats['count']}")
                print(f"    Average: {avg_time}")
                print(f"    Range: {timedelta(seconds=int(stats['min_seconds']))} - {timedelta(seconds=int(stats['max_seconds']))}")
                print(f"    Total: {total_time}")
            
            # Calculate speedup if both methods present
            if 'original' in comparison and 'optimized' in comparison:
                speedup = comparison['original']['avg_seconds'] / comparison['optimized']['avg_seconds']
                time_saved = comparison['original']['avg_seconds'] - comparison['optimized']['avg_seconds']
                
                print(f"\n  📊 SPEEDUP: {speedup:.2f}x faster")
                print(f"  ⏰ TIME SAVED: {timedelta(seconds=int(time_saved))} per run")
        
        print("\n" + "="*70)
        
        # Overall summary
        total_original = sum(
            stats['total_seconds']
            for step_data in self.data['steps'].values()
            for method, stats in self.get_comparison(list(self.data['steps'].keys())[0]).items() if method == 'original'
        ) if any('original' in (self.get_comparison(s) or {}) for s in self.data['steps'].keys()) else 0
        
        total_optimized = sum(
            stats['total_seconds']
            for step_data in self.data['steps'].values()
            for method, stats in self.get_comparison(list(self.data['steps'].keys())[0]).items() if method == 'optimized'
        ) if any('optimized' in (self.get_comparison(s) or {}) for s in self.data['steps'].keys()) else 0
        
        if total_original > 0 and total_optimized > 0:
            print("OVERALL SUMMARY")
            print("="*70)
            print(f"Total Original Time: {timedelta(seconds=int(total_original))}")
            print(f"Total Optimized Time: {timedelta(seconds=int(total_optimized))}")
            print(f"Overall Speedup: {total_original/total_optimized:.2f}x")
            print(f"Total Time Saved: {timedelta(seconds=int(total_original - total_optimized))}")
            print("="*70)


def main():
    """CLI interface."""
    tracker = PerformanceTracker('/media/roy/PortableSSD/InSAR/desc_slc/performance_log.json')
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python performance_tracker.py start <step_name> [method]")
        print("  python performance_tracker.py end <step_name>")
        print("  python performance_tracker.py report")
        print("")
        print("Example:")
        print("  python performance_tracker.py start step_7 optimized")
        print("  # ... processing happens ...")
        print("  python performance_tracker.py end step_7")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == 'start':
        if len(sys.argv) < 3:
            print("❌ Error: step name required")
            print("Usage: python performance_tracker.py start <step_name> [method]")
            sys.exit(1)
        
        step_name = sys.argv[2]
        method = sys.argv[3] if len(sys.argv) > 3 else 'optimized'
        tracker.start_step(step_name, method)
    
    elif command == 'end':
        if len(sys.argv) < 3:
            print("❌ Error: step name required")
            print("Usage: python performance_tracker.py end <step_name>")
            sys.exit(1)
        
        step_name = sys.argv[2]
        tracker.end_step(step_name)
    
    elif command == 'report':
        tracker.print_report()
    
    else:
        print(f"❌ Unknown command: {command}")
        print("Valid commands: start, end, report")
        sys.exit(1)


if __name__ == '__main__':
    main()
