blueprints = custom_target('blueprints',
  input: files(
    'ui/window.blp',
    'ui/composer.blp',
    'ui/history.blp',
    'ui/preferences.blp',
    'ui/role-page.blp',
    'ui/profile-page.blp',
    'ui/add-profile.blp',
    'ui/alt-text-dialog.blp',
    'ui/send-dialog.blp',
    'ui/schedule-dialog.blp',
    'ui/scheduled.blp',
    'ui/shortcuts-dialog.blp',
  ),
  output: '.',
  command: [find_program('blueprint-compiler'), 'batch-compile', '@OUTPUT@', '@CURRENT_SOURCE_DIR@', '@INPUT@'],
)

gnome.compile_resources('dandelion',
  'dandelion.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
  dependencies: blueprints,
)

install_subdir('.', install_dir: moduledir,
  exclude_directories: ['ui', '__pycache__', 'core/__pycache__', 'platforms/__pycache__',
                        'auth/__pycache__', 'net/__pycache__', 'widgets/__pycache__',
                        'ai/__pycache__'],
  exclude_files: ['meson.build', 'dandelion.gresource.xml'],
  strip_directory: true,
)
