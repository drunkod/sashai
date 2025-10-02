#!/usr/bin/env python3
"""
Automatically fix Nix hash mismatches by repeatedly running builds
and updating placeholder hashes with the correct ones.
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

# Default build command
DEFAULT_BUILD_COMMAND = "env -u http_proxy -u https_proxy -u ftp_proxy -u all_proxy -u no_proxy -u HTTP_PROXY -u HTTPS_PROXY -u FTP_PROXY -u ALL_PROXY -u NO_PROXY ~/nixstatic build .#default --keep-failed -L"
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

def run_build_command(command):
    """Run the build command and capture output."""
    logging.info(f"Running command: {command}")
    
    # Security Note: shell=True can be dangerous with untrusted input.
    # Only use this with commands you control.
    process = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    
    return process

def print_summary(replacements, total_time):
    """Print a summary of the operation."""
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    print(f"Total entries updated: {len(replacements)}")
    
    if replacements:
        print("\nUpdated entries:")
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
    
    # Count initial placeholders
    initial_count = count_remaining_placeholders(args.json_file, args.placeholder_hash)
    if initial_count > 0:
        print(f"📊 Found {initial_count} placeholder hash(es) to replace\n")
    else:
        print(f"✨ No placeholder hashes found in {args.json_file}")
        sys.exit(0)
    
    # Main iteration loop
    for iteration in range(args.max_iterations):
        print("="*80)
        print(f"--- ATTEMPT {iteration + 1} ---")
        print(f"Running build command...")
        print("="*80)
        
        # Run the build command
        process = run_build_command(args.build_command)
        
        # Print output (condensed for readability)
        if args.verbose:
            print("--- STDOUT ---")
            print(process.stdout[:2000])  # Limit output
            if len(process.stdout) > 2000:
                print("... (truncated)")
            print("\n--- STDERR ---")
            print(process.stderr)
        else:
            # Show last few lines of error if failed
            if process.returncode != 0:
                stderr_lines = process.stderr.strip().split('\n')
                print("--- BUILD ERROR (last 15 lines) ---")
                for line in stderr_lines[-15:]:
                    print(line)
        
        print("-" * 40)
        
        # Check if the command was successful
        if process.returncode == 0:
            print("\n✅ Build successful! All hashes are correct.")
            break
        
        # Extract revision ID and new hash from error
        rev, new_hash, url = extract_hash_mismatch_info(process.stderr)
        
        if new_hash and rev:
            # Skip if we've already processed this rev (shouldn't happen, but just in case)
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
                
                print(f"📊 Progress: {len(replacements)} entries updated")
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
        
        else:
            # Build failed for another reason
            print("\n❌ Build failed for a reason other than a hash mismatch.")
            
            remaining = count_remaining_placeholders(args.json_file, args.placeholder_hash)
            if remaining > 0:
                print(f"⚠️  Still have {remaining} placeholder(s) but no hash mismatch found.")
                print("This might indicate a different build error.")
            
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
    print_summary(replacements, elapsed_time)
    
    if args.dry_run and replacements:
        print("\n💡 To apply these changes, run without --dry-run")
    
    logging.info(f"Completed. {'Would update' if args.dry_run else 'Updated'} {len(replacements)} entries in {elapsed_time:.2f} seconds")

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