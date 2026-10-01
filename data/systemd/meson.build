systemd_conf = configuration_data()
systemd_conf.set('bindir', get_option('prefix') / get_option('bindir'))

systemd_user_dir = get_option('prefix') / 'lib' / 'systemd' / 'user'
configure_file(
  input: 'dandelion-scheduler.service.in',
  output: 'dandelion-scheduler.service',
  configuration: systemd_conf,
  install_dir: systemd_user_dir,
)
install_data('dandelion-scheduler.timer', install_dir: systemd_user_dir)
