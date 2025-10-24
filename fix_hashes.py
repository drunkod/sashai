#!/usr/bin/env python3
"""
Automatically fix Nix hash mismatches by repeatedly running builds
and updating placeholder hashes with the correct ones.
Enhanced to use ungoogled-chromium section as a reference for hashes.
"""

import subprocess
import re
import sys
import os
import argparse
import shutil
from datetime import datetime
import logging
import json

# --- Configuration ---

# Default build command - using bash with pipefail to get correct exit codes
DEFAULT_BUILD_COMMAND = "bash -c 'set -o pipefail; ~/nixstatic build .#default --keep-failed -L 2>&1 | tee build.log'"
#DEFAULT_BUILD_COMMAND = "~/nixstatic build .#default --keep-failed -L"
# Default file to update
DEFAULT_JSON_FILE = "info.json"

# The placeholder hash used in the file
PLACEHOLDER_HASH = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

# --- Helper Functions ---

def setup_logging(verbose=False):
    """Setup logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f'logs/fix_hashes_{timestamp}.log'
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return log_file

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Automatically fix Nix hash mismatches',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                     # Run with defaults
  %(prog)s --dry-run          # Test without modifying files
  %(prog)s --json-file custom.json  # Use custom JSON file
  %(prog)s --max-iterations 10      # Limit iterations
  %(prog)s --use-ungoogled     # Use ungoogled-chromium hashes as reference
        """
    )
    
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    
    parser.add_argument(
        '--json-file', 
        default=DEFAULT_JSON_FILE,
        help=f'Path to the JSON file to update (default: {DEFAULT_JSON_FILE})'
    )
    
    parser.add_argument(
        '--build-command',
        default=DEFAULT_BUILD_COMMAND,
        help='Custom build command to run'
    )
    
    parser.add_argument(
        '--max-iterations',
        type=int,
        default=50,
        help='Maximum number of iterations (default: 50)'
    )
    
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating backup files'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--placeholder-hash',
        default=PLACEHOLDER_HASH,
        help='Custom placeholder hash to search for'
    )
    
    parser.add_argument(
        '--use-ungoogled',
        action='store_true',
        help='Use ungoogled-chromium section hashes as reference when available'
    )
    
    return parser.parse_args()

def backup_file(filepath):
    """Create a timestamped backup of the file."""
    if not os.path.exists(filepath):
        logging.warning(f"Cannot backup {filepath} - file doesn't exist")
        return None
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.dirname(filepath) or '.'
    filename = os.path.basename(filepath)
    backup_path = os.path.join(backup_dir, f".{filename}.backup_{timestamp}")
    
    try:
        shutil.copy2(filepath, backup_path)
        logging.info(f"Created backup: {backup_path}")
        print(f"📋 Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        logging.error(f"Failed to create backup: {e}")
        return None

def find_hash_in_ungoogled(data, target_rev):
    """
    Find a hash for a given rev in the ungoogled-chromium section.
    Returns the hash if found, None otherwise.
    """
    def search_recursive(obj):
        if isinstance(obj, dict):
            # Check if this dict has both 'rev' and 'hash' fields
            if 'rev' in obj and 'hash' in obj:
                if obj['rev'] == target_rev and obj['hash'] != PLACEHOLDER_HASH:
                    return obj['hash']
            
            # Recursively search in dict values
            for value in obj.values():
                result = search_recursive(value)
                if result:
                    return result
        
        elif isinstance(obj, list):
            # Search in list items
            for item in obj:
                result = search_recursive(item)
                if result:
                    return result
        
        return None
    
    # Search specifically in ungoogled-chromium section
    if 'ungoogled-chromium' in data:
        return search_recursive(data['ungoogled-chromium'])
    return None

def extract_hash_mismatch_info(output):
    """
    Extract revision ID and new hash from build error output.
    Returns: (rev, new_hash, url) or (None, None, None)
    """
    # First, find the hash mismatch
    hash_pattern = r"got:\s+(sha256-[\w+/=]+)"
    hash_match = re.search(hash_pattern, output)
    
    if not hash_match:
        return None, None, None
    
    new_hash = hash_match.group(1)
    
    # Look for the unpacking source archive line to get the rev
    # Pattern: unpacking source archive /build/<rev>.tar.gz
    rev_pattern = r"unpacking source archive /build/([a-f0-9]+)\.tar\.gz"
    rev_match = re.search(rev_pattern, output)
    
    if not rev_match:
        # Try alternative patterns
        # Sometimes it might be in the URL
        url_pattern = r"trying (https://[^\s]+/\+archive/([a-f0-9]+)\.tar\.gz)"
        url_match = re.search(url_pattern, output)
        if url_match:
            url = url_match.group(1).replace('/+archive/' + url_match.group(2) + '.tar.gz', '')
            return url_match.group(2), new_hash, url
        return None, new_hash, None
    
    rev = rev_match.group(1)
    
    # Also try to extract the URL for better context
    url_pattern = r"trying (https://[^\s]+/\+archive/" + re.escape(rev) + r"\.tar\.gz)"
    url_match = re.search(url_pattern, output)
    url = None
    if url_match:
        # Remove the archive part to get base URL
        url = url_match.group(1).replace('/+archive/' + rev + '.tar.gz', '')
    
    return rev, new_hash, url

def find_entry_by_rev(data, target_rev, placeholder_hash):
    """
    Recursively search for an entry with the given rev and placeholder hash.
    Returns: (path_to_entry, entry_dict) or (None, None)
    """
    def search_recursive(obj, path=""):
        if isinstance(obj, dict):
            # Check if this dict has both 'rev' and 'hash' fields
            if 'rev' in obj and 'hash' in obj:
                if obj['rev'] == target_rev and obj['hash'] == placeholder_hash:
                    return path, obj
            
            # Recursively search in dict values
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                result = search_recursive(value, new_path)
                if result[0] is not None:
                    return result
        
        elif isinstance(obj, list):
            # Search in list items
            for i, item in enumerate(obj):
                new_path = f"{path}[{i}]"
                result = search_recursive(item, new_path)
                if result[0] is not None:
                    return result
        
        return None, None
    
    return search_recursive(data)

def update_json_by_rev(filepath, target_rev, new_hash, placeholder_hash, dry_run=False):
    """
    Update the JSON file by finding the entry with the given rev.
    Returns: (success, message, entry_path)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Find the entry with this rev
        entry_path, entry = find_entry_by_rev(data, target_rev, placeholder_hash)
        
        if not entry:
            return False, f"No entry found with rev '{target_rev}' and placeholder hash", None
        
        if dry_run:
            return True, f"Would update hash for entry at path: {entry_path}", entry_path
        
        # Update the hash
        entry['hash'] = new_hash
        
        # Write back to file with nice formatting
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return True, f"Updated hash for entry at path: {entry_path}", entry_path
        
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in file: {e}", None
    except Exception as e:
        return False, f"Error updating file: {e}", None

def get_entry_description(filepath, rev):
    """Get a human-readable description of the entry with the given rev."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        path, entry = find_entry_by_rev(data, rev, PLACEHOLDER_HASH)
        if entry and 'url' in entry:
            # Extract meaningful name from URL
            url = entry['url']
            if 'github.com' in url:
                match = re.search(r'github\.com/([^/]+/[^/]+)', url)
                if match:
                    return match.group(1)
            elif 'chromium.googlesource.com' in url:
                match = re.search(r'chromium\.googlesource\.com/(.+?)(?:\.git)?$', url)
                if match:
                    return match.group(1)
            return url.split('/')[-1].replace('.git', '')
        return rev[:12] + "..."
    except:
        return rev[:12] + "..."

def count_remaining_placeholders(filepath, placeholder_hash):
    """Count remaining placeholders in the JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return content.count(placeholder_hash)
    except:
        return 0

def find_and_update_from_ungoogled(filepath, placeholder_hash, dry_run=False):
    """
    Find placeholder hashes that can be filled from ungoogled-chromium section.
    Returns the number of entries updated.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        updates = []
        
        # Find all entries with placeholder hashes
        def find_placeholders(obj, path=""):
            if isinstance(obj, dict):
                if 'rev' in obj and 'hash' in obj and obj['hash'] == placeholder_hash:
                    # Found a placeholder, check if ungoogled has this rev
                    ungoogled_hash = find_hash_in_ungoogled(data, obj['rev'])
                    if ungoogled_hash:
                        updates.append((path, obj, ungoogled_hash))
                
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    find_placeholders(value, new_path)
            
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_path = f"{path}[{i}]"
                    find_placeholders(item, new_path)
        
        # Skip the ungoogled-chromium section itself
        for key, value in data.items():
            if key != 'ungoogled-chromium':
                find_placeholders(value, key)
        
        if not updates:
            return 0
        
        if dry_run:
            print(f"📦 Found {len(updates)} entries that can be updated from ungoogled-chromium:")
            for path, entry, new_hash in updates:
                print(f"   {path}: {entry['rev'][:12]}... -> {new_hash}")
            return len(updates)
        
        # Apply updates
        for path, entry, new_hash in updates:
            entry['hash'] = new_hash
            print(f"🔄 Updated {path} with hash from ungoogled-chromium")
        
        # Write back to file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return len(updates)
        
    except Exception as e:
        logging.error(f"Error updating from ungoogled: {e}")
        return 0

def run_build_command(command):
    """Run the build command with live output and capture via build.log."""
    logging.info(f"Running command: {command}")
    
    # Run the command
    process = subprocess.run(
        command,
        shell=True,
        capture_output=False,
        text=True,
        encoding='utf-8'
    )
    
    # Read the build.log file to get the output for processing
    build_output = ""
    if os.path.exists("build.log"):
        try:
            with open("build.log", 'r', encoding='utf-8') as f:
                build_output = f.read()
        except Exception as e:
            logging.error(f"Failed to read build.log: {e}")
            build_output = ""
    else:
        logging.warning("build.log not found")
        build_output = ""
    
    # Create a result object
    class Result:
        def __init__(self, returncode, output):
            self.returncode = returncode
            self.stdout = output
            self.stderr = output  # For hash extraction, we need the error output
    
    return Result(process.returncode, build_output)

def print_summary(replacements, ungoogled_updates, total_time):
    """Print a summary of the operation."""
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    print(f"Total entries updated: {len(replacements) + ungoogled_updates}")
    
    if ungoogled_updates > 0:
        print(f"  - From ungoogled-chromium: {ungoogled_updates}")
    
    if replacements:
        print(f"  - From build errors: {len(replacements)}")
        print("\nUpdated entries from build:")
        for i, (rev, new_hash, description) in enumerate(replacements, 1):
            print(f"  {i}. {description}")
            print(f"     Rev: {rev[:12]}...")
            print(f"     Hash: {new_hash}")
    
    print(f"\nTotal time: {total_time:.2f} seconds")
    print("="*80)

def main():
    """Main loop to run the build, fix hashes, and repeat."""
    args = parse_args()
    
    # Setup logging
    log_file = setup_logging(args.verbose)
    
    print("="*80)
    print("🔧 NIX HASH FIXER (Rev-based)")
    print("="*80)
    print(f"JSON File: {args.json_file}")
    print(f"Max Iterations: {args.max_iterations}")
    print(f"Log File: {log_file}")
    print(f"Build Log: build.log")
    print(f"Use Ungoogled: {args.use_ungoogled}")
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be modified")
    
    print("="*80)
    
    # Check if JSON file exists
    if not os.path.exists(args.json_file):
        print(f"❌ Error: File '{args.json_file}' not found")
        logging.error(f"File '{args.json_file}' not found")
        sys.exit(1)
    
    # Validate JSON format
    try:
        with open(args.json_file, 'r', encoding='utf-8') as f:
            json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in '{args.json_file}': {e}")
        sys.exit(1)
    
    # Create initial backup
    if not args.no_backup and not args.dry_run:
        backup_path = backup_file(args.json_file)
        if not backup_path:
            print("⚠️  Warning: Could not create backup, continue anyway? (y/n): ", end='')
            if input().lower() != 'y':
                print("Aborted by user")
                sys.exit(0)
    
    # Track progress
    replacements = []  # List of (rev, new_hash, description) tuples
    start_time = datetime.now()
    processed_revs = set()  # Track which revs we've already processed
    ungoogled_updates = 0
    
    # Count initial placeholders
    initial_count = count_remaining_placeholders(args.json_file, args.placeholder_hash)
    if initial_count > 0:
        print(f"📊 Found {initial_count} placeholder hash(es) to replace\n")
    else:
        print(f"✨ No placeholder hashes found in {args.json_file}")
        sys.exit(0)
    
    # First, try to update from ungoogled-chromium if requested
    if args.use_ungoogled:
        print("🔍 Checking ungoogled-chromium section for matching revisions...")
        ungoogled_updates = find_and_update_from_ungoogled(
            args.json_file, 
            args.placeholder_hash, 
            args.dry_run
        )
        if ungoogled_updates > 0:
            remaining = count_remaining_placeholders(args.json_file, args.placeholder_hash)
            print(f"📊 Updated {ungoogled_updates} entries from ungoogled-chromium")
            print(f"📊 Remaining: {remaining} placeholder(s)\n")
            
            if remaining == 0:
                print("✨ All placeholders have been replaced from ungoogled-chromium!")
                elapsed_time = (datetime.now() - start_time).total_seconds()
                print_summary(replacements, ungoogled_updates, elapsed_time)
                return
    
    # Main iteration loop
    for iteration in range(args.max_iterations):
        print("="*80)
        print(f"--- ATTEMPT {iteration + 1} ---")
        print(f"Running build command...")
        print("="*80)
        
        # Run the build command
        process = run_build_command(args.build_command)
        
        print("-" * 40)
        
        # First check for hash mismatches in the output
        rev, new_hash, url = extract_hash_mismatch_info(process.stderr)
        
        if new_hash and rev:
            # Skip if we've already processed this rev
            if rev in processed_revs:
                print(f"⚠️  Already processed rev {rev[:12]}..., skipping")
                continue
            
            processed_revs.add(rev)
            
            # Get description for this entry
            description = get_entry_description(args.json_file, rev)
            
            print(f"\n💡 Hash mismatch detected!")
            print(f"   Repository: {description}")
            print(f"   Revision: {rev[:12]}...")
            if url:
                print(f"   URL: {url}")
            print(f"   New hash: {new_hash}")
            
            logging.info(f"Found mismatch - Rev: {rev}, Hash: {new_hash}")
            
            # Update the JSON file
            success, message, entry_path = update_json_by_rev(
                args.json_file,
                rev,
                new_hash,
                args.placeholder_hash,
                args.dry_run
            )
            
            if success:
                replacements.append((rev, new_hash, description))
                
                if args.dry_run:
                    print(f"🔍 DRY RUN: {message}")
                else:
                    print(f"🔧 {message}")
                
                remaining = count_remaining_placeholders(args.json_file, args.placeholder_hash)
                
                print(f"📊 Progress: {len(replacements)} entries updated from build")
                print(f"📊 Remaining: {remaining} placeholder(s)")
                
                if remaining == 0:
                    print("\n✨ All placeholders have been replaced!")
                    if not args.dry_run:
                        print("Running final build to verify...")
                    else:
                        break
                
                logging.info(f"Updated entry #{len(replacements)}: {description} (rev: {rev[:12]})")
            else:
                print(f"\n❌ Error: {message}")
                logging.error(f"Failed to update: {message}")
                
                # If entry not found, might be a different type of hash
                if "No entry found" in message:
                    print("This might be a different type of dependency (e.g., npmHash)")
                    print("Skipping and continuing...")
                    continue
        
        elif new_hash:
            # Found hash but no rev - might be npmHash or similar
            print(f"\n💡 Hash mismatch detected (no rev found)")
            print(f"   New hash: {new_hash}")
            print("   This might be npmHash or another non-revision-based hash")
            print("   You may need to update this manually")
            logging.info(f"Found hash without rev: {new_hash}")
            continue
        
        elif process.returncode == 0:
            # Only report success if there was no hash mismatch
            print("\n✅ Build successful! All hashes are correct.")
            break
        
        else:
            # Build failed for another reason (not hash mismatch)
            print("\n❌ Build failed for a reason other than a hash mismatch.")
            
            remaining = count_remaining_placeholders(args.json_file, args.placeholder_hash)
            if remaining > 0:
                print(f"⚠️  Still have {remaining} placeholder(s) but no hash mismatch found.")
                print("This might indicate a different build error.")
                print("Check build.log for full output.")
            
            print("Please review the error above.")
            logging.error("Build failed without hash mismatch")
            sys.exit(1)
    
    else:
        # Loop completed without break
        print(f"\n⚠️  Reached maximum iterations ({args.max_iterations}).")
        print("Stopping to prevent an infinite loop.")
        logging.warning(f"Reached maximum iterations ({args.max_iterations})")
    
    # Print summary
    elapsed_time = (datetime.now() - start_time).total_seconds()
    print_summary(replacements, ungoogled_updates, elapsed_time)
    
    if args.dry_run and (replacements or ungoogled_updates > 0):
        print("\n💡 To apply these changes, run without --dry-run")
    
    logging.info(f"Completed. {'Would update' if args.dry_run else 'Updated'} {len(replacements) + ungoogled_updates} entries in {elapsed_time:.2f} seconds")
    
    # Save final build.log with timestamp if there were updates
    if (replacements or ungoogled_updates > 0) and not args.dry_run:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_log = f"build_final_{timestamp}.log"
        try:
            shutil.copy2("build.log", final_log)
            print(f"\n📋 Final build log saved as: {final_log}")
        except:
            pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        logging.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logging.exception("Unexpected error")
        sys.exit(1)