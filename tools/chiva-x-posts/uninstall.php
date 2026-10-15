<?php
/**
 * Removes the plugin's stored settings, credentials and cache on uninstall.
 */

if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
	exit;
}

delete_option( 'chiva_x_posts_settings' );
delete_option( 'chiva_x_posts_cache' );
delete_option( 'chiva_x_posts_last_error' );
delete_transient( 'chiva_x_posts_lock' );
