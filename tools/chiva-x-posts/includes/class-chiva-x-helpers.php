<?php
/**
 * Pure helpers: OAuth 1.0a signing, response parsing and text formatting.
 * No WordPress dependencies except the escaping functions used in format_text(),
 * so the signing and parsing logic can be tested on its own.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

final class Chiva_X_Helpers {

	/**
	 * OAuth 1.0a HMAC-SHA1 signature (RFC 5849).
	 *
	 * @param string $method          HTTP method.
	 * @param string $url             Base URL without query string.
	 * @param array  $params          Query params + oauth_* params (unencoded).
	 * @param string $consumer_secret API secret.
	 * @param string $token_secret    Access token secret.
	 * @return string Base64 signature.
	 */
	public static function sign( $method, $url, array $params, $consumer_secret, $token_secret ) {
		$encoded = array();
		foreach ( $params as $key => $value ) {
			$encoded[ rawurlencode( (string) $key ) ] = rawurlencode( (string) $value );
		}
		ksort( $encoded, SORT_STRING );

		$pairs = array();
		foreach ( $encoded as $key => $value ) {
			$pairs[] = $key . '=' . $value;
		}

		$base = strtoupper( $method ) . '&' . rawurlencode( $url ) . '&' . rawurlencode( implode( '&', $pairs ) );
		$key  = rawurlencode( $consumer_secret ) . '&' . rawurlencode( $token_secret );

		return base64_encode( hash_hmac( 'sha1', $base, $key, true ) );
	}

	/**
	 * Builds the Authorization header for a signed request.
	 *
	 * @param string $method HTTP method.
	 * @param string $url    Base URL without query string.
	 * @param array  $query  Query params (unencoded).
	 * @param array  $creds  consumer_key, consumer_secret, access_token, access_secret.
	 * @param string $nonce  Random nonce.
	 * @param int    $time   Unix timestamp.
	 * @return string
	 */
	public static function oauth_header( $method, $url, array $query, array $creds, $nonce, $time ) {
		$oauth = array(
			'oauth_consumer_key'     => $creds['consumer_key'],
			'oauth_nonce'            => $nonce,
			'oauth_signature_method' => 'HMAC-SHA1',
			'oauth_timestamp'        => (string) $time,
			'oauth_token'            => $creds['access_token'],
			'oauth_version'          => '1.0',
		);

		$oauth['oauth_signature'] = self::sign(
			$method,
			$url,
			array_merge( $query, $oauth ),
			$creds['consumer_secret'],
			$creds['access_secret']
		);

		$parts = array();
		foreach ( $oauth as $key => $value ) {
			$parts[] = rawurlencode( $key ) . '="' . rawurlencode( $value ) . '"';
		}
		return 'OAuth ' . implode( ', ', $parts );
	}

	/**
	 * Reduces an X API v2 user-timeline response to what the widget needs.
	 *
	 * @param array $json  Decoded response.
	 * @param int   $count How many posts to keep.
	 * @return array List of posts: id, text, created_at, urls[].
	 */
	public static function parse_timeline( array $json, $count ) {
		$posts = array();
		if ( empty( $json['data'] ) || ! is_array( $json['data'] ) ) {
			return $posts;
		}

		foreach ( $json['data'] as $item ) {
			if ( empty( $item['id'] ) || ! isset( $item['text'] ) ) {
				continue;
			}
			$urls = array();
			if ( ! empty( $item['entities']['urls'] ) && is_array( $item['entities']['urls'] ) ) {
				foreach ( $item['entities']['urls'] as $u ) {
					if ( empty( $u['url'] ) ) {
						continue;
					}
					$urls[] = array(
						'url'          => (string) $u['url'],
						'expanded_url' => isset( $u['expanded_url'] ) ? (string) $u['expanded_url'] : (string) $u['url'],
						'display_url'  => isset( $u['display_url'] ) ? (string) $u['display_url'] : (string) $u['url'],
					);
				}
			}
			$posts[] = array(
				'id'         => (string) $item['id'],
				'text'       => (string) $item['text'],
				'created_at' => isset( $item['created_at'] ) ? (string) $item['created_at'] : '',
				'urls'       => $urls,
			);
			if ( count( $posts ) >= $count ) {
				break;
			}
		}
		return $posts;
	}

	/**
	 * Escapes post text and turns t.co links into readable links.
	 *
	 * @param string $text Raw post text from the API.
	 * @param array  $urls URL entities from parse_timeline().
	 * @return string Safe HTML.
	 */
	public static function format_text( $text, array $urls ) {
		$html = esc_html( html_entity_decode( $text, ENT_QUOTES | ENT_HTML5, 'UTF-8' ) );

		foreach ( $urls as $u ) {
			$link = sprintf(
				'<a href="%s" rel="nofollow noopener" target="_blank">%s</a>',
				esc_url( $u['expanded_url'] ),
				esc_html( $u['display_url'] )
			);
			$html = str_replace( esc_html( $u['url'] ), $link, $html );
		}

		return nl2br( $html );
	}
}
