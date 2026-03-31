#!/usr/bin/env python3

import sys
import os
import json
import asyncio
import concurrent.futures
from datetime import datetime
import argparse

# Add the indices directories to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'rsi'))
sys.path.append(os.path.join(current_dir, 'fear_greed'))
sys.path.append(os.path.join(current_dir, 'vix'))
sys.path.append(os.path.join(current_dir, 'dxy'))
sys.path.append(os.path.join(current_dir, 'buffett'))

# Fetcher modules are imported lazily inside fetch_single_indicator

class IndicatorOrchestrator:
    # Map of indicator names to (module_path, class_name)
    FETCHER_MAP = {
        'rsi':               ('fetch_rsi',               'RSIFetcher'),
        'fear_greed':        ('fetch_fear_greed',        'FearGreedFetcher'),
        'vix':               ('fetch_vix',               'VIXFetcher'),
        'dxy':               ('fetch_dxy',               'DXYFetcher'),
        'buffett_indicator': ('fetch_buffett_indicator', 'BuffettIndicatorFetcher'),
    }

    def __init__(self):
        self.fetchers = list(self.FETCHER_MAP.keys())
        
        self.results = {}
        
    def fetch_single_indicator(self, indicator_name, **kwargs):
        """Fetch a single indicator (lazy-imports the fetcher module)"""
        try:
            if indicator_name not in self.FETCHER_MAP:
                return {
                    'indicator': indicator_name,
                    'status': 'error',
                    'error': f'Unknown indicator: {indicator_name}',
                    'timestamp': datetime.now().isoformat()
                }

            module_name, class_name = self.FETCHER_MAP[indicator_name]
            import importlib
            module = importlib.import_module(module_name)
            fetcher_class = getattr(module, class_name)
            fetcher = fetcher_class()

            result = fetcher.run()
            result_status = result.get('status', 'error') if isinstance(result, dict) else 'error'

            return {
                'indicator': indicator_name,
                'status': 'success' if result_status == 'success' else 'error',
                'data': result,
                'error': None if result_status == 'success' else result.get('error', f'{indicator_name} fetch failed'),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            return {
                'indicator': indicator_name,
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def fetch_all_indicators(self, indicators=None, parallel=True, **kwargs):
        """Fetch all or specified indicators"""
        if indicators is None:
            indicators = list(self.FETCHER_MAP.keys())
        
        if parallel:
            return self._fetch_parallel(indicators, **kwargs)
        else:
            return self._fetch_sequential(indicators, **kwargs)
    
    def _fetch_sequential(self, indicators, **kwargs):
        """Fetch indicators one by one"""
        results = {}
        
        for indicator in indicators:
            print(f"\n📊 Fetching {indicator.upper()}...")
            result = self.fetch_single_indicator(indicator, **kwargs)
            results[indicator] = result
            
            if result['status'] == 'success':
                print(f"✅ {indicator.upper()} fetched successfully")
            else:
                print(f"❌ {indicator.upper()} failed: {result.get('error', 'Unknown error')}")
        
        return results
    
    def _fetch_parallel(self, indicators, max_workers=3, **kwargs):
        """Fetch indicators in parallel"""
        results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_indicator = {
                executor.submit(self.fetch_single_indicator, indicator, **kwargs): indicator 
                for indicator in indicators
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_indicator):
                indicator = future_to_indicator[future]
                try:
                    result = future.result()
                    results[indicator] = result
                    
                    if result['status'] == 'success':
                        print(f"✅ {indicator.upper()} fetched successfully")
                    else:
                        print(f"❌ {indicator.upper()} failed: {result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    results[indicator] = {
                        'indicator': indicator,
                        'status': 'error',
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }
                    print(f"❌ {indicator.upper()} failed with exception: {e}")
        
        return results
    
    def save_summary(self, results, filename="fetch_summary.json"):
        """Save a summary of all fetch operations"""
        summary = {
            'fetch_timestamp': datetime.now().isoformat(),
            'total_indicators': len(results),
            'successful': sum(1 for r in results.values() if r['status'] == 'success'),
            'failed': sum(1 for r in results.values() if r['status'] == 'error'),
            'results': results
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            print(f"\n📄 Summary saved to {filename}")
        except Exception as e:
            print(f"❌ Failed to save summary: {e}")
        
        return summary
    
    def print_summary(self, results):
        """Print a summary of the fetch operation"""
        print("\n" + "="*50)
        print("📊 FINANCIAL INDICATORS FETCH SUMMARY")
        print("="*50)
        
        successful = 0
        failed = 0
        
        for indicator, result in results.items():
            status_icon = "✅" if result['status'] == 'success' else "❌"
            print(f"{status_icon} {indicator.upper():<20} - {result['status']}")
            
            if result['status'] == 'success':
                successful += 1
                # Print key data if available
                if 'data' in result and result['data']:
                    data = result['data']
                    if indicator == 'rsi' and data.get('rsi'):
                        print(f"   └─ RSI: {data['rsi']}")
                    elif indicator == 'fear_greed' and data.get('index_value'):
                        print(f"   └─ Index: {data['index_value']} ({data.get('label', '')})")
                    elif indicator == 'vix' and data.get('value'):
                        print(f"   └─ VIX: {data['value']}")
                    elif indicator == 'dxy' and data.get('value'):
                        print(f"   └─ DXY: {data['value']}")
                    elif indicator == 'buffett_indicator' and data.get('percentage'):
                        print(f"   └─ Buffett: {data['percentage']}% ({data.get('valuation_level', '')})")
            else:
                failed += 1
                if 'error' in result:
                    print(f"   └─ Error: {result['error'][:50]}...")
        
        print("-"*50)
        print(f"📈 Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📊 Total: {len(results)}")
        print("="*50)

def main():
    parser = argparse.ArgumentParser(description='Fetch financial indicators')
    parser.add_argument('--indicators', '-i', nargs='+', 
                       choices=['rsi', 'fear_greed', 'vix', 'dxy', 'buffett_indicator'],
                       help='Specific indicators to fetch (default: all)')
    parser.add_argument('--sequential', '-s', action='store_true',
                       help='Run fetchers sequentially instead of parallel')
    parser.add_argument('--output', '-o', default='fetch_summary.json',
                       help='Output file for summary (default: fetch_summary.json)')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Suppress detailed output')
    
    args = parser.parse_args()
    
    orchestrator = IndicatorOrchestrator()
    
    # Prepare kwargs
    kwargs = {}
    
    # Run the fetchers
    print("🚀 Starting financial indicators fetch...")
    print(f"⏱️  Timestamp: {datetime.now().isoformat()}")
    
    if args.indicators:
        print(f"📋 Fetching specific indicators: {', '.join(args.indicators)}")
        results = orchestrator.fetch_all_indicators(
            indicators=args.indicators,
            parallel=not args.sequential,
            **kwargs
        )
    else:
        print("📋 Fetching all indicators...")
        results = orchestrator.fetch_all_indicators(
            parallel=not args.sequential,
            **kwargs
        )
    
    # Print and save results
    if not args.quiet:
        orchestrator.print_summary(results)
    
    summary = orchestrator.save_summary(results, args.output)
    
    # Exit with appropriate code
    failed_count = sum(1 for r in results.values() if r['status'] == 'error')
    sys.exit(0 if failed_count == 0 else 1)

if __name__ == "__main__":
    main()
