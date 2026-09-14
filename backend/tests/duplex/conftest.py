import sys, types

# Mock gssapi to avoid Kerberos dependency on Windows
for mod_name in ['gssapi', 'gssapi._win_config']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)
