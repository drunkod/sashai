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
      packages = forAllSystems (system:
        let
          pkgs = pkgsFor.${system};
        in
        {
          default = pkgs.callPackage ./default.nix { };
        });

      apps = forAllSystems (system:
        let
          pkgs = pkgsFor.${system};
        in
        {
          default = {
            type = "app";
            program = "${self.packages.${system}.default}/bin/chromium";
          };
          
          update-chromium = {
            type = "app";
            program = "${pkgs.writeShellScriptBin "update-chromium" ''
              #!/usr/bin/env bash
              set -e
              export PATH=${pkgs.git}/bin:$PATH
              ${pkgs.zx}/bin/zx "${self}/update.mjs" --chromium "$@"
            ''}/bin/update-chromium";
          };
        });

      # Development shell for running scripts manually
      devShells = forAllSystems (system:
        let
          pkgs = pkgsFor.${system};
          # Read info.json to get the depot_tools rev/hash for the shell
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
              # Tools needed to run and manage scripts
              pkgs.python3
              pkgs.jq
              pkgs.curl
              pkgs.git
              pkgs.zx
            ];

            # Set environment variables for the shell
            shellHook = ''
              # Make the depot_tools path easily accessible
              export DEPOT_TOOLS_PATH="${depot-tools-pkg}"
              
              echo "--- SashAI Development Shell ---"
              echo ""
              echo "Welcome! This shell contains the tools to manually update Chromium dependencies."
              echo "The path to depot_tools is available as \$DEPOT_TOOLS_PATH"
              echo ""
              echo "--- MANUAL WORKFLOW TO POPULATE DEPS ---"
              echo ""
              echo "  1. Find the Git commit for your target version (e.g., 142.0.7444.0):"
              echo "     REV=$(curl -sfL "https://chromium.googlesource.com/chromium/src/+/refs/tags/142.0.7444.0?format=json" | sed "1d" | jq -r '.commit')"
              echo ""
              echo "  2. Run depot_tools.py with this revision:"
              echo "     python3 ./depot_tools.py \$DEPOT_TOOLS_PATH \$REV > new_deps.json"
              echo ""
              echo "  3. Manually copy the contents of 'new_deps.json' into the 'DEPS' object in 'info.json'."
              echo ""
              echo "-------------------------------------"
            '';
          };
        });

      defaultPackage = self.packages.x86_64-linux.default;
      defaultApp = self.apps.x86_64-linux.default;
    };
}