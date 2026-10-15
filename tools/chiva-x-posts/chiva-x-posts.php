<?php
/**
 * Plugin Name:       Chiva X Posts
 * Description:       Shows your latest posts from X in a sidebar widget or with the [chiva_x_posts] shortcode. Uses the X API v2 with caching, so pay-per-use costs stay at cents per month.
 * Version:           1.0.0
 * Requires at least: 5.8
 * Requires PHP:      7.4
 * Author:            Luis Orozco
 * License:           GPL-2.0-or-later
 * Text Domain:       chiva-x-posts
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

require_once __DIR__ . '/includes/class-chiva-x-helpers.php';

final class Chiva_X_Posts {

	const OPT_SETTINGS = 'chiva_x_posts_settings';
	const OPT_CACHE    = 'chiva_x_posts_cache';
	const OPT_ERROR    = 'chiva_x_posts_last_error';
	const LOCK         = 'chiva_x_posts_lock';
	const API          = 'https://api.x.com/2';
	const PAGE         = 'chiva-x-posts';

	/** Retry delay after a failed fetch, so errors never hammer the paid API. */
	const RETRY_AFTER = 15 * 60;

	public static function init() {
		add_action( 'widgets_init', array( __CLASS__, 'register_widget' ) );
		add_shortcode( 'chiva_x_posts', array( __CLASS__, 'shortcode' ) );
		add_action( 'wp_enqueue_scripts', array( __CLASS__, 'styles' ) );
		add_action( 'admin_menu', array( __CLASS__, 'admin_menu' ) );
		add_action( 'admin_init', array( __CLASS__, 'register_settings' ) );
		add_action( 'admin_post_chiva_x_posts_refresh', array( __CLASS__, 'handle_refresh' ) );
		add_action( 'update_option_' . self::OPT_SETTINGS, array( __CLASS__, 'settings_changed' ), 10, 0 );
	}

	/* ---------- Settings ---------- */

	public static function defaults() {
		return array(
			'consumer_key'     => '',
			'consumer_secret'  => '',
			'access_token'     => '',
			'access_secret'    => '',
			'count'            => 5,
			'refresh_hours'    => 3,
			'exclude_replies'  => 1,
			'exclude_retweets' => 1,
		);
	}

	public static function settings() {
		return wp_parse_args( (array) get_option( self::OPT_SETTINGS, array() ), self::defaults() );
	}

	private static function has_credentials( array $s ) {
		return '' !== $s['consumer_key'] && '' !== $s['consumer_secret']
			&& '' !== $s['access_token'] && '' !== $s['access_secret'];
	}

	public static function register_settings() {
		register_setting(
			'chiva_x_posts',
			self::OPT_SETTINGS,
			array( 'sanitize_callback' => array( __CLASS__, 'sanitize' ) )
		);
	}

	public static function sanitize( $input ) {
		$old   = self::settings();
		$input = is_array( $input ) ? $input : array();
		$out   = $old;

		// Secrets: an empty field means "keep the saved value".
		foreach ( array( 'consumer_key', 'consumer_secret', 'access_token', 'access_secret' ) as $key ) {
			if ( isset( $input[ $key ] ) && '' !== trim( $input[ $key ] ) ) {
				$out[ $key ] = sanitize_text_field( $input[ $key ] );
			}
		}

		$out['count']            = min( 10, max( 1, absint( $input['count'] ?? $old['count'] ) ) );
		$out['refresh_hours']    = min( 24, max( 1, absint( $input['refresh_hours'] ?? $old['refresh_hours'] ) ) );
		$out['exclude_replies']  = empty( $input['exclude_replies'] ) ? 0 : 1;
		$out['exclude_retweets'] = empty( $input['exclude_retweets'] ) ? 0 : 1;

		return $out;
	}

	/** Credentials or filters changed: drop the cache so the next view fetches fresh data. */
	public static function settings_changed() {
		delete_option( self::OPT_CACHE );
		delete_option( self::OPT_ERROR );
	}

	/* ---------- Fetching ---------- */

	/**
	 * Returns cached posts, refreshing from the API when the cache is older than the refresh interval.
	 * On any API error the last good posts are kept and shown.
	 */
	public static function get_data( $force = false ) {
		$s     = self::settings();
		$cache = (array) get_option( self::OPT_CACHE, array() );
		$ttl   = (int) $s['refresh_hours'] * HOUR_IN_SECONDS;
		$age   = time() - (int) ( $cache['fetched'] ?? 0 );

		if ( ! self::has_credentials( $s ) ) {
			return $cache;
		}
		if ( ! $force && $age < $ttl ) {
			return $cache;
		}
		if ( get_transient( self::LOCK ) ) {
			return $cache; // Another request is already refreshing.
		}

		set_transient( self::LOCK, 1, MINUTE_IN_SECONDS );
		$result = self::fetch( $s, $cache );
		delete_transient( self::LOCK );

		if ( is_wp_error( $result ) ) {
			update_option(
				self::OPT_ERROR,
				array(
					'time'    => time(),
					'message' => $result->get_error_message(),
				),
				false
			);
			// Keep the old posts, and retry after RETRY_AFTER rather than on every page view.
			$cache['fetched'] = time() - $ttl + self::RETRY_AFTER;
			update_option( self::OPT_CACHE, $cache, false );
			return $cache;
		}

		delete_option( self::OPT_ERROR );
		update_option( self::OPT_CACHE, $result, false );
		return $result;
	}

	private static function fetch( array $s, array $cache ) {
		// Resolve the account once; it is cached with the posts.
		$user = $cache['user'] ?? null;
		if ( empty( $user['id'] ) ) {
			$me = self::request( '/users/me', array(), $s );
			if ( is_wp_error( $me ) ) {
				return $me;
			}
			if ( empty( $me['data']['id'] ) ) {
				return new WP_Error( 'chiva_x_no_user', __( 'Could not identify the X account for these credentials.', 'chiva-x-posts' ) );
			}
			$user = array(
				'id'       => (string) $me['data']['id'],
				'username' => (string) ( $me['data']['username'] ?? '' ),
			);
		}

		$query = array(
			// The API returns at least 5; extra posts are discarded locally.
			'max_results'  => (string) max( 5, (int) $s['count'] ),
			'tweet.fields' => 'created_at,entities',
		);
		$exclude = array();
		if ( $s['exclude_replies'] ) {
			$exclude[] = 'replies';
		}
		if ( $s['exclude_retweets'] ) {
			$exclude[] = 'retweets';
		}
		if ( $exclude ) {
			$query['exclude'] = implode( ',', $exclude );
		}

		$json = self::request( '/users/' . rawurlencode( $user['id'] ) . '/tweets', $query, $s );
		if ( is_wp_error( $json ) ) {
			return $json;
		}

		return array(
			'fetched' => time(),
			'user'    => $user,
			// Keep everything returned (already paid for); render() trims to the display count.
			'posts'   => Chiva_X_Helpers::parse_timeline( $json, max( 5, (int) $s['count'] ) ),
		);
	}

	private static function request( $path, array $query, array $s ) {
		$url    = self::API . $path;
		$header = Chiva_X_Helpers::oauth_header(
			'GET',
			$url,
			$query,
			$s,
			wp_generate_password( 32, false, false ),
			time()
		);

		$full = $query ? $url . '?' . http_build_query( $query, '', '&', PHP_QUERY_RFC3986 ) : $url;

		$response = wp_remote_get(
			$full,
			array(
				'timeout' => 10,
				'headers' => array(
					'Authorization' => $header,
					'Accept'        => 'application/json',
				),
			)
		);

		if ( is_wp_error( $response ) ) {
			return $response;
		}

		$code = (int) wp_remote_retrieve_response_code( $response );
		$body = json_decode( wp_remote_retrieve_body( $response ), true );

		if ( 200 !== $code ) {
			$detail = '';
			if ( is_array( $body ) ) {
				$detail = $body['detail'] ?? ( $body['title'] ?? ( $body['errors'][0]['message'] ?? '' ) );
			}
			if ( 401 === $code || 403 === $code ) {
				/* translators: %d: HTTP status code. */
				$msg = sprintf( __( 'X rejected the credentials or the app lacks access (HTTP %d). Check the keys, that the app has Read permission, and that the account has API credit.', 'chiva-x-posts' ), $code );
			} elseif ( 402 === $code ) {
				$msg = __( 'X reports no available API credit (HTTP 402). Add credit in the X Developer Console.', 'chiva-x-posts' );
			} elseif ( 429 === $code ) {
				$msg = __( 'X rate limit reached (HTTP 429). The widget keeps showing the last posts and will retry later.', 'chiva-x-posts' );
			} else {
				/* translators: %d: HTTP status code. */
				$msg = sprintf( __( 'X API error (HTTP %d).', 'chiva-x-posts' ), $code );
			}
			if ( $detail ) {
				$msg .= ' ' . $detail;
			}
			return new WP_Error( 'chiva_x_http_' . $code, $msg );
		}

		if ( ! is_array( $body ) ) {
			return new WP_Error( 'chiva_x_bad_json', __( 'X returned a response that could not be read.', 'chiva-x-posts' ) );
		}
		return $body;
	}

	/* ---------- Output ---------- */

	public static function render( $count = null ) {
		$data  = self::get_data();
		$posts = $data['posts'] ?? array();
		$user  = $data['user']['username'] ?? '';

		if ( null === $count ) {
			$count = (int) self::settings()['count'];
		}
		$posts = array_slice( $posts, 0, max( 1, (int) $count ) );

		if ( ! $posts ) {
			return '<div class="chiva-x-posts chiva-x-posts--empty">' . esc_html__( 'No posts to show yet.', 'chiva-x-posts' ) . '</div>';
		}

		$html = '<ul class="chiva-x-posts">';
		foreach ( $posts as $post ) {
			$permalink = $user
				? 'https://x.com/' . rawurlencode( $user ) . '/status/' . rawurlencode( $post['id'] )
				: 'https://x.com/i/web/status/' . rawurlencode( $post['id'] );

			$when = '';
			$ts   = $post['created_at'] ? strtotime( $post['created_at'] ) : false;
			if ( $ts ) {
				/* translators: %s: human-readable time difference, e.g. "3 hours". */
				$when = sprintf( __( '%s ago', 'chiva-x-posts' ), human_time_diff( $ts, time() ) );
			}

			$html .= '<li class="chiva-x-posts__item">';
			$html .= '<p class="chiva-x-posts__text">' . Chiva_X_Helpers::format_text( $post['text'], $post['urls'] ) . '</p>';
			if ( $when ) {
				$html .= '<a class="chiva-x-posts__time" href="' . esc_url( $permalink ) . '" rel="nofollow noopener" target="_blank">' . esc_html( $when ) . '</a>';
			}
			$html .= '</li>';
		}
		$html .= '</ul>';

		if ( $user ) {
			$html .= '<p class="chiva-x-posts__follow"><a href="' . esc_url( 'https://x.com/' . rawurlencode( $user ) ) . '" rel="nofollow noopener" target="_blank">'
				/* translators: %s: X username. */
				. esc_html( sprintf( __( 'Follow @%s on X', 'chiva-x-posts' ), $user ) ) . '</a></p>';
		}

		return $html;
	}

	public static function shortcode( $atts ) {
		$atts = shortcode_atts( array( 'count' => null ), $atts, 'chiva_x_posts' );
		return self::render( null === $atts['count'] ? null : (int) $atts['count'] );
	}

	public static function styles() {
		wp_register_style( 'chiva-x-posts', false, array(), '1.0.0' );
		wp_enqueue_style( 'chiva-x-posts' );
		wp_add_inline_style(
			'chiva-x-posts',
			'.chiva-x-posts{list-style:none;margin:0;padding:0}'
			. '.chiva-x-posts__item{margin:0 0 1em;padding:0 0 1em;border-bottom:1px solid rgba(127,127,127,.25)}'
			. '.chiva-x-posts__item:last-child{border-bottom:0}'
			. '.chiva-x-posts__text{margin:0 0 .35em;overflow-wrap:anywhere}'
			. '.chiva-x-posts__time{font-size:.85em;opacity:.75}'
			. '.chiva-x-posts__follow{font-size:.9em;margin-top:.5em}'
		);
	}

	public static function register_widget() {
		register_widget( 'Chiva_X_Posts_Widget' );
	}

	/* ---------- Admin ---------- */

	public static function admin_menu() {
		add_options_page(
			__( 'X Posts', 'chiva-x-posts' ),
			__( 'X Posts', 'chiva-x-posts' ),
			'manage_options',
			self::PAGE,
			array( __CLASS__, 'settings_page' )
		);
	}

	public static function handle_refresh() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_die( esc_html__( 'Not allowed.', 'chiva-x-posts' ) );
		}
		check_admin_referer( 'chiva_x_posts_refresh' );
		self::get_data( true );
		wp_safe_redirect( admin_url( 'options-general.php?page=' . self::PAGE . '&refreshed=1' ) );
		exit;
	}

	public static function settings_page() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		$s     = self::settings();
		$cache = (array) get_option( self::OPT_CACHE, array() );
		$error = get_option( self::OPT_ERROR );
		$name  = self::OPT_SETTINGS;

		$fetches_per_day = 24 / max( 1, (int) $s['refresh_hours'] );
		$posts_per_fetch = max( 5, (int) $s['count'] );
		$owned_month     = $fetches_per_day * $posts_per_fetch * 0.001 * 30;
		$standard_month  = $fetches_per_day * $posts_per_fetch * 0.005 * 30;
		?>
		<div class="wrap">
			<h1><?php esc_html_e( 'X Posts', 'chiva-x-posts' ); ?></h1>

			<?php if ( isset( $_GET['refreshed'] ) ) : // phpcs:ignore WordPress.Security.NonceVerification.Recommended ?>
				<div class="notice notice-info is-dismissible"><p><?php esc_html_e( 'Refresh attempted. See the status below.', 'chiva-x-posts' ); ?></p></div>
			<?php endif; ?>

			<h2><?php esc_html_e( 'Status', 'chiva-x-posts' ); ?></h2>
			<ul>
				<li><?php esc_html_e( 'Account:', 'chiva-x-posts' ); ?>
					<strong><?php echo ! empty( $cache['user']['username'] ) ? esc_html( '@' . $cache['user']['username'] ) : esc_html__( 'not connected yet', 'chiva-x-posts' ); ?></strong></li>
				<li><?php esc_html_e( 'Last successful fetch:', 'chiva-x-posts' ); ?>
					<strong><?php echo ! empty( $cache['posts'] ) && ! empty( $cache['fetched'] ) ? esc_html( wp_date( 'Y-m-d H:i', (int) $cache['fetched'] ) ) : esc_html__( 'never', 'chiva-x-posts' ); ?></strong></li>
				<?php if ( is_array( $error ) && ! empty( $error['message'] ) ) : ?>
					<li style="color:#b32d2e"><?php esc_html_e( 'Last error:', 'chiva-x-posts' ); ?>
						<?php echo esc_html( wp_date( 'Y-m-d H:i', (int) $error['time'] ) . ' — ' . $error['message'] ); ?></li>
				<?php endif; ?>
			</ul>
			<form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
				<input type="hidden" name="action" value="chiva_x_posts_refresh">
				<?php wp_nonce_field( 'chiva_x_posts_refresh' ); ?>
				<?php submit_button( __( 'Refresh now', 'chiva-x-posts' ), 'secondary', 'submit', false ); ?>
			</form>

			<h2><?php esc_html_e( 'Settings', 'chiva-x-posts' ); ?></h2>
			<form method="post" action="options.php">
				<?php settings_fields( 'chiva_x_posts' ); ?>
				<table class="form-table" role="presentation">
					<?php
					$secrets = array(
						'consumer_key'    => __( 'API Key (consumer key)', 'chiva-x-posts' ),
						'consumer_secret' => __( 'API Key Secret', 'chiva-x-posts' ),
						'access_token'    => __( 'Access Token', 'chiva-x-posts' ),
						'access_secret'   => __( 'Access Token Secret', 'chiva-x-posts' ),
					);
					foreach ( $secrets as $key => $label ) :
						?>
						<tr>
							<th scope="row"><label for="<?php echo esc_attr( $key ); ?>"><?php echo esc_html( $label ); ?></label></th>
							<td>
								<input type="password" class="regular-text" autocomplete="off" id="<?php echo esc_attr( $key ); ?>"
									name="<?php echo esc_attr( $name . '[' . $key . ']' ); ?>" value=""
									placeholder="<?php echo '' !== $s[ $key ] ? esc_attr__( 'Saved — leave blank to keep', 'chiva-x-posts' ) : ''; ?>">
							</td>
						</tr>
					<?php endforeach; ?>
					<tr>
						<th scope="row"><label for="count"><?php esc_html_e( 'Posts to show', 'chiva-x-posts' ); ?></label></th>
						<td><input type="number" min="1" max="10" id="count" name="<?php echo esc_attr( $name ); ?>[count]" value="<?php echo esc_attr( $s['count'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><label for="refresh_hours"><?php esc_html_e( 'Refresh every (hours)', 'chiva-x-posts' ); ?></label></th>
						<td><input type="number" min="1" max="24" id="refresh_hours" name="<?php echo esc_attr( $name ); ?>[refresh_hours]" value="<?php echo esc_attr( $s['refresh_hours'] ); ?>"></td>
					</tr>
					<tr>
						<th scope="row"><?php esc_html_e( 'Filter', 'chiva-x-posts' ); ?></th>
						<td>
							<label><input type="checkbox" name="<?php echo esc_attr( $name ); ?>[exclude_replies]" value="1" <?php checked( $s['exclude_replies'], 1 ); ?>> <?php esc_html_e( 'Hide replies', 'chiva-x-posts' ); ?></label><br>
							<label><input type="checkbox" name="<?php echo esc_attr( $name ); ?>[exclude_retweets]" value="1" <?php checked( $s['exclude_retweets'], 1 ); ?>> <?php esc_html_e( 'Hide reposts', 'chiva-x-posts' ); ?></label>
						</td>
					</tr>
				</table>
				<p class="description">
					<?php
					printf(
						/* translators: 1: fetches per day, 2: posts per fetch, 3: monthly cost at owned-read rate, 4: monthly cost at standard rate. */
						esc_html__( 'Estimated API cost: %1$s fetches/day × %2$s posts ≈ $%3$s/month at the owned-read rate ($0.001/post), at most $%4$s/month at the standard read rate ($0.005/post). Check current prices in the X Developer Console.', 'chiva-x-posts' ),
						esc_html( number_format_i18n( $fetches_per_day, 1 ) ),
						esc_html( $posts_per_fetch ),
						esc_html( number_format_i18n( $owned_month, 2 ) ),
						esc_html( number_format_i18n( $standard_month, 2 ) )
					);
					?>
				</p>
				<?php submit_button(); ?>
			</form>

			<h2><?php esc_html_e( 'Use it', 'chiva-x-posts' ); ?></h2>
			<p><?php esc_html_e( 'Add the "X Posts" widget to your sidebar (Appearance → Widgets), or use a Shortcode block with:', 'chiva-x-posts' ); ?> <code>[chiva_x_posts]</code> <?php esc_html_e( 'or', 'chiva-x-posts' ); ?> <code>[chiva_x_posts count="3"]</code></p>
		</div>
		<?php
	}
}

final class Chiva_X_Posts_Widget extends WP_Widget {

	public function __construct() {
		parent::__construct(
			'chiva_x_posts',
			__( 'X Posts', 'chiva-x-posts' ),
			array( 'description' => __( 'Your latest posts from X.', 'chiva-x-posts' ) )
		);
	}

	public function widget( $args, $instance ) {
		$title = apply_filters( 'widget_title', $instance['title'] ?? '', $instance, $this->id_base );
		$count = ! empty( $instance['count'] ) ? (int) $instance['count'] : null;

		echo $args['before_widget']; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- theme markup.
		if ( $title ) {
			echo $args['before_title'] . esc_html( $title ) . $args['after_title']; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped
		}
		echo Chiva_X_Posts::render( $count ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- escaped in render().
		echo $args['after_widget']; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped
	}

	public function form( $instance ) {
		$title = $instance['title'] ?? __( 'Latest on X', 'chiva-x-posts' );
		$count = $instance['count'] ?? '';
		?>
		<p>
			<label for="<?php echo esc_attr( $this->get_field_id( 'title' ) ); ?>"><?php esc_html_e( 'Title:', 'chiva-x-posts' ); ?></label>
			<input class="widefat" id="<?php echo esc_attr( $this->get_field_id( 'title' ) ); ?>" name="<?php echo esc_attr( $this->get_field_name( 'title' ) ); ?>" type="text" value="<?php echo esc_attr( $title ); ?>">
		</p>
		<p>
			<label for="<?php echo esc_attr( $this->get_field_id( 'count' ) ); ?>"><?php esc_html_e( 'Posts to show (blank = plugin setting):', 'chiva-x-posts' ); ?></label>
			<input class="tiny-text" id="<?php echo esc_attr( $this->get_field_id( 'count' ) ); ?>" name="<?php echo esc_attr( $this->get_field_name( 'count' ) ); ?>" type="number" min="1" max="10" value="<?php echo esc_attr( $count ); ?>">
		</p>
		<?php
	}

	public function update( $new_instance, $old_instance ) {
		return array(
			'title' => sanitize_text_field( $new_instance['title'] ?? '' ),
			'count' => '' === ( $new_instance['count'] ?? '' ) ? '' : min( 10, max( 1, absint( $new_instance['count'] ) ) ),
		);
	}
}

Chiva_X_Posts::init();
