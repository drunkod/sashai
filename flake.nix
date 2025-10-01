{
  description = "SashAI Browser - A standalone flake for development";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/e643668fd71b949c53f8626614b21ff71a07379d";
  };

  outputs = { self, nixpkgs }:
    let
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      pkgsFor = forAllSystems (system: import nixpkgs {
        inherit system;
      });
    in
    {
      # -------------------------------------------------------------------
      #   1. PACKAGES: Defines what 'nix build' will produce.
      # -------------------------------------------------------------------
      packages = forAllSystems (system:
        let
          pkgs = pkgsFor.${system};
        in
        {
          default = pkgs.callPackage ./default.nix { };
        });

      # -------------------------------------------------------------------
      #   2. APPS: Defines runnable scripts for 'nix run'.
      # -------------------------------------------------------------------
      apps = forAllSystems (system:
        let
          pkgs = pkgsFor.${system};
          # Read info.json to get the depot_tools rev/hash needed for the scripts.
          sashai-info = builtins.fromJSON (builtins.readFile ./info.json);
          depot-tools-pkg = pkgs.fetchFromGitiles {
            url = "https://chromium.googlesource.com/chromium/tools/depot_tools.git";
            rev = sashai-info.chromium.deps.depot_tools.rev;
            hash = sashai-info.chromium.deps.depot_tools.hash;
          };
        in
        {
          # --- App to RUN the browser ---
          default = {
            type = "app";
            program = "${self.packages.${system}.default}/bin/chromium";
          };
          
          # --- App to SET a specific version (Primary Update Tool) ---
          # This is the most reliable script. It does everything in one go.
          # Usage: nix run .#set-chromium-version -- 142.0.7444.0
          set-chromium-version = {
            type = "app";
            program = "${pkgs.writeShellScriptBin "set-chromium-version" ''
              #!/usr/bin/env bash
              set -euo pipefail

              if [ -z "$1" ]; then
                echo "Error: Please provide a Chromium version as an argument."
                echo "Usage: nix run .#set-chromium-version -- <version>"
                exit 1
              fi

              VERSION="$1"
              echo "--- Setting Chromium version to $VERSION ---"

              if [ ! -f "info.json" ] || [ ! -f "depot_tools.py" ]; then
                echo "Error: Make sure 'info.json' and 'depot_tools.py' are in the current directory."
                exit 1
              fi

              # 1. Resolve version to git commit revision
              echo "[1/3] Resolving version to commit hash..."
              COMMIT_URL="https://chromium.googlesource.com/chromium/src/+/refs/tags/$VERSION?format=json"
              REV=$(${pkgs.curl}/bin/curl -sfL "$COMMIT_URL" | sed "1d" | ${pkgs.jq}/bin/jq -r '.commit')
              if [ -z "$REV" ] || [ "$REV" == "null" ]; then
                echo "Error: Could not resolve version '$VERSION' to a git commit."
                exit 1
              fi
              echo "  > Found commit revision: $REV"

              # 2. Run python script to resolve DEPS
              echo "[2/3] Running depot_tools.py to resolve all dependencies..."
              DEPS_JSON=$(${pkgs.python3}/bin/python3 ./depot_tools.py "${depot-tools-pkg}" "$REV")
              echo "  > Successfully generated DEPS list."

              # 3. Update info.json with all new information and clean it up
              echo "[3/3] Updating info.json..."
              TMP_JSON=$(mktemp)
              ${pkgs.jq}/bin/jq \
                --arg version "$VERSION" \
                --arg rev "$REV" \
                --argjson deps "$DEPS_JSON" \
                '
                  # Update top-level version info
                  .chromium.version = $version |
                  .chromium.chromedriver.version = $version |
                  # Replace the DEPS object and remove the "fetcher" key from every dependency
                  .chromium.DEPS = ($deps | map_values(del(.fetcher))) |
                  # Ensure the main src rev is correct and reset hashes
                  .chromium.DEPS.src.rev = $rev |
                  .chromium.DEPS.src.hash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=" |
                  .chromium.deps.npmHash = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
                ' \
                info.json > "$TMP_JSON" && mv "$TMP_JSON" info.json
              echo "  > info.json has been fully updated."

              echo ""
              echo "✓ Success! Your project is now configured for Chromium $VERSION."
              echo ""
              echo "---------------- NEXT STEPS ----------------"
              echo "Run the build to find the correct hashes:"
              echo "  nix build .#default --keep-failed -L"
              echo "------------------------------------------"
            ''}/bin/set-chromium-version";
          };

          # --- App to DISCOVER the latest version on a channel ---
          # Use this to find out what version to use with set-chromium-version.
          # Usage: nix run .#update-chromium -- --channel canary
          update-chromium = {
            type = "app";
            program = "${pkgs.writeShellScriptBin "update-chromium" ''
              #!/usr/bin/env bash
              set -e
              export PATH=${pkgs.git}/bin:$PATH
              # Pass all arguments through to the zx script
              ${pkgs.zx}/bin/zx "${self}/update.mjs" --chromium "$@"
            ''}/bin/update-chromium";
          };
        });

      # -------------------------------------------------------------------
      #   3. DEV SHELL: For manual debugging and fine-grained control.
      # -------------------------------------------------------------------
      devShells = forAllSystems (system:
        let
          pkgs = pkgsFor.${system};
          sashai-info = builtins.fromJSON (builtins.readFile ./info.json);
          depot-tools-pkg = pkgs.fetchFromGitiles {
            url = "https://chromium.googlesource.com/chromium/tools/depot_tools.git";
            rev = sashai-info.chromium.deps.depot_tools.rev;
            hash = sashai-info.chromium.deps.depot_tools.hash;
          };
        in
        {
          default = pkgs.mkShell {
            packages = [
              pkgs.python3
              pkgs.jq
              pkgs.curl
              pkgs.git
              pkgs.zx
            ];

            shellHook = ''
              export DEPOT_TOOLS_PATH="${depot-tools-pkg}"
              
              echo "--- SashAI Development Shell ---"
              echo "Welcome! The path to depot_tools is available as \$DEPOT_TOOLS_PATH"
              echo ""
              echo "--- WORKFLOW TO POPULATE DEPS MANUALLY ---"
              echo "  1. Find the Git commit for your target version:"
              echo "     REV=\$(curl -sfL \"https://chromium.googlesource.com/chromium/src/+/refs/tags/YOUR_VERSION_HERE?format=json\" | sed \"1d\" | jq -r '.commit')"
              echo ""
              echo "  2. Run depot_tools.py and clean the output:"
              echo "     python3 ./depot_tools.py \$DEPOT_TOOLS_PATH \$REV | jq 'map_values(del(.fetcher))' > new_deps.json"
              echo ""
              echo "  3. Manually copy from 'new_deps.json' into the 'DEPS' object in 'info.json'."
              echo "-------------------------------------"
            '';
          };
        });

      # --- Default package and app for convenience ---
      defaultPackage = self.packages.x86_64-linux.default;
      defaultApp = self.apps.x86_64-linux.default;
    };
}