project('dandelion',
          version: '0.2.1',
    meson_version: '>= 1.4.0',
  default_options: [ 'warning_level=2', 'werror=false', ],
          license: 'GPL-3.0-or-later',
)

i18n = import('i18n')
gnome = import('gnome')
python = import('python')

application_id = 'de.linuxundich.Dandelion'
pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'dandelion'

py_installation = python.find_installation('python3')

subdir('data')
subdir('bin')
subdir('src')
subdir('po')

gnome.post_install(
     glib_compile_schemas: true,
    gtk_update_icon_cache: true,
  update_desktop_database: true,
)
