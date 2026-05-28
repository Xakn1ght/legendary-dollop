--
-- PostgreSQL database dump
--

\restrict w91lJThbRRcncfhs4gNjALoqIGkAEbquHTC7wxmGa5cyIlyy8YDZ6DxYh3zcl4D

-- Dumped from database version 18.3 (Ubuntu 18.3-1)
-- Dumped by pg_dump version 18.3 (Ubuntu 18.3-1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: achievements; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.achievements (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text NOT NULL,
    icon character varying(50),
    requirement_type character varying(50) NOT NULL,
    requirement_value integer NOT NULL,
    reward_type character varying(50) NOT NULL,
    reward_value character varying(100) NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.achievements OWNER TO astronaut_admin;

--
-- Name: achievements_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.achievements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.achievements_id_seq OWNER TO astronaut_admin;

--
-- Name: achievements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.achievements_id_seq OWNED BY public.achievements.id;


--
-- Name: challenges; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.challenges (
    id integer NOT NULL,
    title character varying(100) NOT NULL,
    description text NOT NULL,
    challenge_type character varying(50) NOT NULL,
    requirement_type character varying(50) NOT NULL,
    requirement_value integer NOT NULL,
    reward_type character varying(50) NOT NULL,
    reward_value integer NOT NULL,
    start_date timestamp without time zone NOT NULL,
    end_date timestamp without time zone NOT NULL,
    active boolean NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.challenges OWNER TO astronaut_admin;

--
-- Name: challenges_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.challenges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.challenges_id_seq OWNER TO astronaut_admin;

--
-- Name: challenges_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.challenges_id_seq OWNED BY public.challenges.id;


--
-- Name: charge_requests; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.charge_requests (
    id integer NOT NULL,
    subscription_id integer NOT NULL,
    user_id integer NOT NULL,
    traffic_bytes bigint NOT NULL,
    extra_days integer,
    price integer NOT NULL,
    charge_type character varying(32),
    receipt_message_id integer,
    receipt_image_url character varying,
    status character varying,
    created_at timestamp without time zone
);


ALTER TABLE public.charge_requests OWNER TO astronaut_admin;

--
-- Name: charge_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.charge_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.charge_requests_id_seq OWNER TO astronaut_admin;

--
-- Name: charge_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.charge_requests_id_seq OWNED BY public.charge_requests.id;


--
-- Name: daily_game_plays; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.daily_game_plays (
    id integer NOT NULL,
    user_id integer NOT NULL,
    play_date date NOT NULL,
    best_score integer NOT NULL,
    duration_seconds integer NOT NULL,
    display_name character varying(40) NOT NULL,
    rewarded boolean NOT NULL,
    streak_on_play integer NOT NULL,
    reward_credit integer NOT NULL,
    reward_stars integer NOT NULL,
    reward_xp integer NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.daily_game_plays OWNER TO astronaut_admin;

--
-- Name: daily_game_plays_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.daily_game_plays_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.daily_game_plays_id_seq OWNER TO astronaut_admin;

--
-- Name: daily_game_plays_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.daily_game_plays_id_seq OWNED BY public.daily_game_plays.id;


--
-- Name: daily_star_caps; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.daily_star_caps (
    id integer NOT NULL,
    user_id integer NOT NULL,
    date date NOT NULL,
    stars_earned integer NOT NULL,
    max_allowed integer NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


ALTER TABLE public.daily_star_caps OWNER TO astronaut_admin;

--
-- Name: daily_star_caps_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.daily_star_caps_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.daily_star_caps_id_seq OWNER TO astronaut_admin;

--
-- Name: daily_star_caps_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.daily_star_caps_id_seq OWNED BY public.daily_star_caps.id;


--
-- Name: leaderboards; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.leaderboards (
    id integer NOT NULL,
    user_id integer NOT NULL,
    category character varying(50) NOT NULL,
    score integer NOT NULL,
    rank integer,
    period character varying(20) NOT NULL,
    date timestamp without time zone NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.leaderboards OWNER TO astronaut_admin;

--
-- Name: leaderboards_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.leaderboards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.leaderboards_id_seq OWNER TO astronaut_admin;

--
-- Name: leaderboards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.leaderboards_id_seq OWNED BY public.leaderboards.id;


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.notifications (
    id integer NOT NULL,
    user_id integer NOT NULL,
    type character varying(32) NOT NULL,
    title character varying(255) NOT NULL,
    message text NOT NULL,
    ticket_id integer,
    read boolean NOT NULL,
    read_at timestamp without time zone,
    sent_to_webapp boolean NOT NULL,
    sent_to_bot boolean NOT NULL,
    bot_message_sent boolean NOT NULL,
    bot_message_id bigint,
    created_at timestamp without time zone
);


ALTER TABLE public.notifications OWNER TO astronaut_admin;

--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notifications_id_seq OWNER TO astronaut_admin;

--
-- Name: notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;


--
-- Name: pending_deletion_requests; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.pending_deletion_requests (
    id integer NOT NULL,
    user_id integer NOT NULL,
    subscription_id integer NOT NULL,
    subscription_username character varying NOT NULL,
    reason character varying,
    status character varying,
    created_at timestamp without time zone,
    processed_at timestamp without time zone,
    processed_by integer
);


ALTER TABLE public.pending_deletion_requests OWNER TO astronaut_admin;

--
-- Name: pending_deletion_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.pending_deletion_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.pending_deletion_requests_id_seq OWNER TO astronaut_admin;

--
-- Name: pending_deletion_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.pending_deletion_requests_id_seq OWNED BY public.pending_deletion_requests.id;


--
-- Name: receipts; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.receipts (
    id integer NOT NULL,
    user_id integer NOT NULL,
    subscription_id integer,
    plan_name character varying,
    price integer,
    paid_amount integer,
    status character varying,
    created_at timestamp without time zone
);


ALTER TABLE public.receipts OWNER TO astronaut_admin;

--
-- Name: receipts_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.receipts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.receipts_id_seq OWNER TO astronaut_admin;

--
-- Name: receipts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.receipts_id_seq OWNED BY public.receipts.id;


--
-- Name: referral_rewards; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.referral_rewards (
    id integer NOT NULL,
    subscription_id integer NOT NULL,
    referrer_id integer NOT NULL,
    reward_value integer,
    traffic_bytes bigint,
    extra_days integer,
    credit_amount integer,
    spent boolean NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.referral_rewards OWNER TO astronaut_admin;

--
-- Name: referral_rewards_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.referral_rewards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.referral_rewards_id_seq OWNER TO astronaut_admin;

--
-- Name: referral_rewards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.referral_rewards_id_seq OWNED BY public.referral_rewards.id;


--
-- Name: referrals; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.referrals (
    id integer NOT NULL,
    referrer_id integer,
    referee_id integer,
    created_at timestamp without time zone
);


ALTER TABLE public.referrals OWNER TO astronaut_admin;

--
-- Name: referrals_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.referrals_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.referrals_id_seq OWNER TO astronaut_admin;

--
-- Name: referrals_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.referrals_id_seq OWNED BY public.referrals.id;


--
-- Name: renewal_history; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.renewal_history (
    id integer NOT NULL,
    subscription_id integer NOT NULL,
    renewed_at timestamp without time zone,
    result character varying NOT NULL,
    details character varying
);


ALTER TABLE public.renewal_history OWNER TO astronaut_admin;

--
-- Name: renewal_history_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.renewal_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.renewal_history_id_seq OWNER TO astronaut_admin;

--
-- Name: renewal_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.renewal_history_id_seq OWNED BY public.renewal_history.id;


--
-- Name: reward_config; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.reward_config (
    id integer NOT NULL,
    traffic_percent double precision NOT NULL,
    days_percent double precision NOT NULL,
    credit_percent double precision NOT NULL
);


ALTER TABLE public.reward_config OWNER TO astronaut_admin;

--
-- Name: reward_effectiveness; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.reward_effectiveness (
    id integer NOT NULL,
    reward_type character varying(50) NOT NULL,
    total_given integer NOT NULL,
    total_redeemed integer NOT NULL,
    conversion_rate double precision NOT NULL,
    date timestamp without time zone NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.reward_effectiveness OWNER TO astronaut_admin;

--
-- Name: reward_effectiveness_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.reward_effectiveness_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reward_effectiveness_id_seq OWNER TO astronaut_admin;

--
-- Name: reward_effectiveness_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.reward_effectiveness_id_seq OWNED BY public.reward_effectiveness.id;


--
-- Name: reward_history; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.reward_history (
    id integer NOT NULL,
    user_id integer NOT NULL,
    reward_type character varying(50) NOT NULL,
    reward_value integer NOT NULL,
    source character varying(50) NOT NULL,
    source_id integer,
    notes character varying,
    earned_at timestamp without time zone,
    spent_at timestamp without time zone
);


ALTER TABLE public.reward_history OWNER TO astronaut_admin;

--
-- Name: reward_history_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.reward_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reward_history_id_seq OWNER TO astronaut_admin;

--
-- Name: reward_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.reward_history_id_seq OWNED BY public.reward_history.id;


--
-- Name: seasonal_events; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.seasonal_events (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text NOT NULL,
    event_type character varying(50) NOT NULL,
    start_date timestamp without time zone NOT NULL,
    end_date timestamp without time zone NOT NULL,
    reward_multiplier double precision NOT NULL,
    active boolean NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.seasonal_events OWNER TO astronaut_admin;

--
-- Name: seasonal_events_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.seasonal_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.seasonal_events_id_seq OWNER TO astronaut_admin;

--
-- Name: seasonal_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.seasonal_events_id_seq OWNED BY public.seasonal_events.id;


--
-- Name: star_history; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.star_history (
    id integer NOT NULL,
    user_id integer NOT NULL,
    delta integer NOT NULL,
    reason character varying(50) NOT NULL,
    source_id integer,
    notes character varying(200),
    created_at timestamp without time zone
);


ALTER TABLE public.star_history OWNER TO astronaut_admin;

--
-- Name: star_history_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.star_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.star_history_id_seq OWNER TO astronaut_admin;

--
-- Name: star_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.star_history_id_seq OWNED BY public.star_history.id;


--
-- Name: star_reward_tiers; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.star_reward_tiers (
    id integer NOT NULL,
    star_threshold integer NOT NULL,
    title character varying(100) NOT NULL,
    description text NOT NULL,
    reward_type character varying(50) NOT NULL,
    reward_value character varying(100) NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.star_reward_tiers OWNER TO astronaut_admin;

--
-- Name: star_reward_tiers_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.star_reward_tiers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.star_reward_tiers_id_seq OWNER TO astronaut_admin;

--
-- Name: star_reward_tiers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.star_reward_tiers_id_seq OWNED BY public.star_reward_tiers.id;


--
-- Name: subscription_links; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.subscription_links (
    user_id integer NOT NULL,
    subscription_id integer NOT NULL,
    added_at timestamp without time zone
);


ALTER TABLE public.subscription_links OWNER TO astronaut_admin;

--
-- Name: subscriptions; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.subscriptions (
    id integer NOT NULL,
    user_id integer,
    referrer_id integer,
    marzban_username character varying,
    sub_token character varying,
    plan_name character varying,
    price integer,
    status character varying,
    receipt_message_id integer,
    admin_receipt_forward_message_id bigint,
    admin_request_message_id bigint,
    receipt_image_url character varying,
    user_link_sent boolean NOT NULL,
    low_data_notified boolean NOT NULL,
    imminent_expiry_notified boolean NOT NULL,
    expired_notified boolean NOT NULL,
    created_at timestamp without time zone,
    renewal_paid boolean NOT NULL,
    renewal_template character varying,
    renewal_price integer,
    renewal_requested_at timestamp without time zone,
    renewal_applied boolean NOT NULL,
    credit_used integer,
    applied_discount_ids character varying,
    carry_over_bytes bigint,
    carry_over_reset_at timestamp without time zone
);


ALTER TABLE public.subscriptions OWNER TO astronaut_admin;

--
-- Name: subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.subscriptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.subscriptions_id_seq OWNER TO astronaut_admin;

--
-- Name: subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.subscriptions_id_seq OWNED BY public.subscriptions.id;


--
-- Name: ticket_messages; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.ticket_messages (
    id integer NOT NULL,
    ticket_id integer NOT NULL,
    sender character varying(16) NOT NULL,
    content_type character varying(16) NOT NULL,
    text text,
    telegram_message_id bigint,
    file_id character varying,
    reply_to_message_id bigint,
    replied_to integer,
    file_unique_id character varying,
    file_name character varying,
    file_size integer,
    file_mime_type character varying,
    voice_duration integer,
    read_by_admin boolean,
    read_by_user boolean,
    created_at timestamp without time zone
);


ALTER TABLE public.ticket_messages OWNER TO astronaut_admin;

--
-- Name: ticket_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.ticket_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.ticket_messages_id_seq OWNER TO astronaut_admin;

--
-- Name: ticket_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.ticket_messages_id_seq OWNED BY public.ticket_messages.id;


--
-- Name: tickets; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.tickets (
    id integer NOT NULL,
    user_id integer NOT NULL,
    subscription_id integer,
    user_ticket_number integer NOT NULL,
    category character varying(32) NOT NULL,
    subject character varying(80) NOT NULL,
    status character varying(16) NOT NULL,
    priority character varying(16) NOT NULL,
    os character varying(32),
    isp character varying(64),
    assigned_admin_id integer,
    allow_more_from_user boolean NOT NULL,
    notify_on_reply boolean NOT NULL,
    hidden_from_user boolean NOT NULL,
    hidden_at timestamp without time zone,
    is_private_chat boolean NOT NULL,
    chat_invitation_sent boolean NOT NULL,
    chat_invitation_accepted boolean NOT NULL,
    chat_invitation_expired boolean NOT NULL,
    chat_invitation_sent_at timestamp without time zone,
    chat_started_at timestamp without time zone,
    chat_ended_at timestamp without time zone,
    last_message_at timestamp without time zone,
    last_reminder_at timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    closed_at timestamp without time zone,
    resolved boolean NOT NULL,
    feedback_score integer,
    feedback_text text
);


ALTER TABLE public.tickets OWNER TO astronaut_admin;

--
-- Name: tickets_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.tickets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tickets_id_seq OWNER TO astronaut_admin;

--
-- Name: tickets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.tickets_id_seq OWNED BY public.tickets.id;


--
-- Name: user_achievements; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.user_achievements (
    id integer NOT NULL,
    user_id integer NOT NULL,
    achievement_id integer NOT NULL,
    earned_at timestamp without time zone
);


ALTER TABLE public.user_achievements OWNER TO astronaut_admin;

--
-- Name: user_achievements_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.user_achievements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_achievements_id_seq OWNER TO astronaut_admin;

--
-- Name: user_achievements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.user_achievements_id_seq OWNED BY public.user_achievements.id;


--
-- Name: user_analytics; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.user_analytics (
    id integer NOT NULL,
    user_id integer NOT NULL,
    date timestamp without time zone NOT NULL,
    login_count integer NOT NULL,
    referral_clicks integer NOT NULL,
    reward_redemptions integer NOT NULL,
    subscription_usage_bytes bigint NOT NULL,
    created_at timestamp without time zone
);


ALTER TABLE public.user_analytics OWNER TO astronaut_admin;

--
-- Name: user_analytics_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.user_analytics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_analytics_id_seq OWNER TO astronaut_admin;

--
-- Name: user_analytics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.user_analytics_id_seq OWNED BY public.user_analytics.id;


--
-- Name: user_challenges; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.user_challenges (
    id integer NOT NULL,
    user_id integer NOT NULL,
    challenge_id integer NOT NULL,
    progress integer NOT NULL,
    completed boolean NOT NULL,
    completed_at timestamp without time zone,
    created_at timestamp without time zone
);


ALTER TABLE public.user_challenges OWNER TO astronaut_admin;

--
-- Name: user_challenges_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.user_challenges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_challenges_id_seq OWNER TO astronaut_admin;

--
-- Name: user_challenges_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.user_challenges_id_seq OWNED BY public.user_challenges.id;


--
-- Name: user_discounts; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.user_discounts (
    id integer NOT NULL,
    user_id integer NOT NULL,
    percent integer NOT NULL,
    expiration timestamp without time zone NOT NULL,
    used boolean NOT NULL,
    source character varying(50)
);


ALTER TABLE public.user_discounts OWNER TO astronaut_admin;

--
-- Name: user_discounts_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.user_discounts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_discounts_id_seq OWNER TO astronaut_admin;

--
-- Name: user_discounts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.user_discounts_id_seq OWNED BY public.user_discounts.id;


--
-- Name: user_gifts; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.user_gifts (
    id integer NOT NULL,
    sender_id integer NOT NULL,
    receiver_id integer NOT NULL,
    gift_type character varying(50) NOT NULL,
    gift_value integer NOT NULL,
    plan_name character varying(100),
    message text,
    payment_status character varying(20) NOT NULL,
    payment_receipt_message_id bigint,
    accepted boolean NOT NULL,
    accepted_at timestamp without time zone,
    created_at timestamp without time zone
);


ALTER TABLE public.user_gifts OWNER TO astronaut_admin;

--
-- Name: user_gifts_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.user_gifts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_gifts_id_seq OWNER TO astronaut_admin;

--
-- Name: user_gifts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.user_gifts_id_seq OWNED BY public.user_gifts.id;


--
-- Name: user_star_reward_claims; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.user_star_reward_claims (
    id integer NOT NULL,
    user_id integer NOT NULL,
    tier_id integer NOT NULL,
    offered_at timestamp without time zone,
    expires_at timestamp without time zone NOT NULL,
    claimed_at timestamp without time zone,
    chosen_reward_type character varying(50),
    status character varying(50) NOT NULL
);


ALTER TABLE public.user_star_reward_claims OWNER TO astronaut_admin;

--
-- Name: user_star_reward_claims_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.user_star_reward_claims_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.user_star_reward_claims_id_seq OWNER TO astronaut_admin;

--
-- Name: user_star_reward_claims_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.user_star_reward_claims_id_seq OWNED BY public.user_star_reward_claims.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.users (
    id integer NOT NULL,
    chat_id bigint NOT NULL,
    username character varying,
    full_name character varying,
    language character varying(8) NOT NULL,
    dashboard_prefs text NOT NULL,
    referral_code character varying,
    phone_number character varying,
    created_at timestamp without time zone,
    stars integer NOT NULL,
    credit integer NOT NULL,
    banned boolean NOT NULL,
    is_admin boolean NOT NULL,
    category character varying(32) NOT NULL,
    level integer NOT NULL,
    experience_points integer NOT NULL,
    last_daily_login timestamp without time zone,
    login_streak integer NOT NULL,
    loyalty_points integer NOT NULL,
    custom_username character varying,
    star_pieces integer NOT NULL,
    arcade_stars_this_month integer NOT NULL,
    arcade_stars_month_reset date,
    show_on_leaderboard boolean NOT NULL,
    is_vip boolean NOT NULL,
    vip_until timestamp without time zone,
    discount_percent integer DEFAULT 0 NOT NULL,
    discount_expiration timestamp without time zone
);


ALTER TABLE public.users OWNER TO astronaut_admin;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO astronaut_admin;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: vip_orders; Type: TABLE; Schema: public; Owner: astronaut_admin
--

CREATE TABLE public.vip_orders (
    id integer NOT NULL,
    user_id integer NOT NULL,
    plan_id character varying NOT NULL,
    days integer,
    price integer NOT NULL,
    receipt_image_url character varying,
    status character varying,
    created_at timestamp without time zone,
    approved_at timestamp without time zone,
    approved_by integer
);


ALTER TABLE public.vip_orders OWNER TO astronaut_admin;

--
-- Name: vip_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: astronaut_admin
--

CREATE SEQUENCE public.vip_orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.vip_orders_id_seq OWNER TO astronaut_admin;

--
-- Name: vip_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: astronaut_admin
--

ALTER SEQUENCE public.vip_orders_id_seq OWNED BY public.vip_orders.id;


--
-- Name: achievements id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.achievements ALTER COLUMN id SET DEFAULT nextval('public.achievements_id_seq'::regclass);


--
-- Name: challenges id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.challenges ALTER COLUMN id SET DEFAULT nextval('public.challenges_id_seq'::regclass);


--
-- Name: charge_requests id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.charge_requests ALTER COLUMN id SET DEFAULT nextval('public.charge_requests_id_seq'::regclass);


--
-- Name: daily_game_plays id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.daily_game_plays ALTER COLUMN id SET DEFAULT nextval('public.daily_game_plays_id_seq'::regclass);


--
-- Name: daily_star_caps id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.daily_star_caps ALTER COLUMN id SET DEFAULT nextval('public.daily_star_caps_id_seq'::regclass);


--
-- Name: leaderboards id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.leaderboards ALTER COLUMN id SET DEFAULT nextval('public.leaderboards_id_seq'::regclass);


--
-- Name: notifications id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);


--
-- Name: pending_deletion_requests id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.pending_deletion_requests ALTER COLUMN id SET DEFAULT nextval('public.pending_deletion_requests_id_seq'::regclass);


--
-- Name: receipts id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.receipts ALTER COLUMN id SET DEFAULT nextval('public.receipts_id_seq'::regclass);


--
-- Name: referral_rewards id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.referral_rewards ALTER COLUMN id SET DEFAULT nextval('public.referral_rewards_id_seq'::regclass);


--
-- Name: referrals id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.referrals ALTER COLUMN id SET DEFAULT nextval('public.referrals_id_seq'::regclass);


--
-- Name: renewal_history id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.renewal_history ALTER COLUMN id SET DEFAULT nextval('public.renewal_history_id_seq'::regclass);


--
-- Name: reward_effectiveness id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.reward_effectiveness ALTER COLUMN id SET DEFAULT nextval('public.reward_effectiveness_id_seq'::regclass);


--
-- Name: reward_history id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.reward_history ALTER COLUMN id SET DEFAULT nextval('public.reward_history_id_seq'::regclass);


--
-- Name: seasonal_events id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.seasonal_events ALTER COLUMN id SET DEFAULT nextval('public.seasonal_events_id_seq'::regclass);


--
-- Name: star_history id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.star_history ALTER COLUMN id SET DEFAULT nextval('public.star_history_id_seq'::regclass);


--
-- Name: star_reward_tiers id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.star_reward_tiers ALTER COLUMN id SET DEFAULT nextval('public.star_reward_tiers_id_seq'::regclass);


--
-- Name: subscriptions id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.subscriptions ALTER COLUMN id SET DEFAULT nextval('public.subscriptions_id_seq'::regclass);


--
-- Name: ticket_messages id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.ticket_messages ALTER COLUMN id SET DEFAULT nextval('public.ticket_messages_id_seq'::regclass);


--
-- Name: tickets id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.tickets ALTER COLUMN id SET DEFAULT nextval('public.tickets_id_seq'::regclass);


--
-- Name: user_achievements id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_achievements ALTER COLUMN id SET DEFAULT nextval('public.user_achievements_id_seq'::regclass);


--
-- Name: user_analytics id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_analytics ALTER COLUMN id SET DEFAULT nextval('public.user_analytics_id_seq'::regclass);


--
-- Name: user_challenges id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_challenges ALTER COLUMN id SET DEFAULT nextval('public.user_challenges_id_seq'::regclass);


--
-- Name: user_discounts id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_discounts ALTER COLUMN id SET DEFAULT nextval('public.user_discounts_id_seq'::regclass);


--
-- Name: user_gifts id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_gifts ALTER COLUMN id SET DEFAULT nextval('public.user_gifts_id_seq'::regclass);


--
-- Name: user_star_reward_claims id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_star_reward_claims ALTER COLUMN id SET DEFAULT nextval('public.user_star_reward_claims_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: vip_orders id; Type: DEFAULT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.vip_orders ALTER COLUMN id SET DEFAULT nextval('public.vip_orders_id_seq'::regclass);


--
-- Data for Name: achievements; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.achievements (id, name, description, icon, requirement_type, requirement_value, reward_type, reward_value, created_at) FROM stdin;
1	بلند پرواز	اولین بازی خود را انجام دهید	🚀	game_plays	1	bundle	credit:500|xp:100	2026-05-19 16:17:16.923182
2	اولین تماس	اولین دوست خود را معرفی کنید	🎯	referrals	1	bundle	credit:2000|xp:200	2026-05-19 16:17:16.923998
3	رهبر گروه	۵ نفر را معرفی کنید	👥	referrals	5	bundle	credit:10000|xp:500|stars:1	2026-05-19 16:17:16.924429
4	امپراتوری کهکشانی	۲۰ معرفی فعال (خرید پلن ۲۰GB+)	🌌	active_referrals	20	bundle	credit:50000|xp:1200|stars:3	2026-05-19 16:17:16.92487
5	مسافر داده	۵۰ گیگابایت داده مصرف کنید	📡	usage	50	bundle	credit:5000|xp:300	2026-05-19 16:17:16.925259
6	فرمانده داده	۲۰۰ گیگابایت داده مصرف کنید	📊	usage	200	bundle	credit:20000|xp:800	2026-05-19 16:17:16.925684
7	جنگجوی نوار	۷ روز متوالی بازی کنید	🔥	play_streak	7	bundle	credit:5000|xp:400	2026-05-19 16:17:16.926102
8	مسافر زمان	۳۰ روز متوالی بازی کنید	⏰	play_streak	30	bundle	credit:25000|xp:1200|stars:2	2026-05-19 16:17:16.926494
9	خریدار بزرگ	۵ اشتراک خریداری کنید	💎	purchases	5	bundle	xp:800|stars:1|cashback:5	2026-05-19 16:17:16.926866
10	حامی	۱۰ اشتراک خریداری کنید	👑	purchases	10	bundle	xp:2000|stars:2|cashback:10	2026-05-19 16:17:16.927233
11	امتیاز کامل	در بازی به ۱۵۰۰۰+ امتیاز برسید	🏆	high_score	15000	bundle	credit:5000|xp:500|stars:1	2026-05-19 16:17:16.927654
\.


--
-- Data for Name: challenges; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.challenges (id, title, description, challenge_type, requirement_type, requirement_value, reward_type, reward_value, start_date, end_date, active, created_at) FROM stdin;
1	ورود روزانه	امروز وارد شوید	daily	logins	1	xp	10	2026-05-19 00:00:00	2026-05-19 23:59:59.999999	t	2026-05-19 16:17:16.92943
2	معرفی هفتگی	۳ نفر را این هفته معرفی کنید	weekly	referrals	3	loyalty_points	100	2026-05-18 16:17:16.928833	2026-05-25 16:17:16.928833	t	2026-05-19 16:17:16.930223
3	بازی روزانه	یک بار بازی روزانه انجام دهید	daily	daily_game	1	xp	20	2026-05-19 00:00:00	2026-05-19 23:59:59.999999	t	2026-05-19 16:17:16.930692
4	امتیاز بازی هفتگی	این هفته به امتیاز مشخصی در بازی برسید	weekly	weekly_game_score	3000	loyalty_points	150	2026-05-18 16:17:16.928833	2026-05-25 16:17:16.928833	t	2026-05-19 16:17:16.931111
\.


--
-- Data for Name: charge_requests; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.charge_requests (id, subscription_id, user_id, traffic_bytes, extra_days, price, charge_type, receipt_message_id, receipt_image_url, status, created_at) FROM stdin;
\.


--
-- Data for Name: daily_game_plays; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.daily_game_plays (id, user_id, play_date, best_score, duration_seconds, display_name, rewarded, streak_on_play, reward_credit, reward_stars, reward_xp, created_at) FROM stdin;
\.


--
-- Data for Name: daily_star_caps; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.daily_star_caps (id, user_id, date, stars_earned, max_allowed, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: leaderboards; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.leaderboards (id, user_id, category, score, rank, period, date, created_at) FROM stdin;
1	1	referrals	0	\N	all_time	2026-05-20 11:55:50.24518	2026-05-19 19:14:14.176127
2	1	activity	0	\N	all_time	2026-05-20 11:55:50.320296	2026-05-19 19:14:14.186847
3	1	usage	0	\N	all_time	2026-05-20 11:55:50.328264	2026-05-19 19:14:14.19499
4	1	spending	0	\N	all_time	2026-05-20 11:55:50.335362	2026-05-19 19:14:14.20884
5	2	referrals	0	\N	all_time	2026-05-20 11:55:50.349211	2026-05-19 19:14:14.231995
6	2	activity	0	\N	all_time	2026-05-20 11:55:50.35442	2026-05-19 19:14:14.237938
7	2	usage	0	\N	all_time	2026-05-20 11:55:50.380169	2026-05-19 19:14:14.909604
8	2	spending	1	\N	all_time	2026-05-20 11:55:50.385668	2026-05-19 19:14:14.916021
\.


--
-- Data for Name: notifications; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.notifications (id, user_id, type, title, message, ticket_id, read, read_at, sent_to_webapp, sent_to_bot, bot_message_sent, bot_message_id, created_at) FROM stdin;
\.


--
-- Data for Name: pending_deletion_requests; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.pending_deletion_requests (id, user_id, subscription_id, subscription_username, reason, status, created_at, processed_at, processed_by) FROM stdin;
\.


--
-- Data for Name: receipts; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.receipts (id, user_id, subscription_id, plan_name, price, paid_amount, status, created_at) FROM stdin;
\.


--
-- Data for Name: referral_rewards; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.referral_rewards (id, subscription_id, referrer_id, reward_value, traffic_bytes, extra_days, credit_amount, spent, created_at) FROM stdin;
\.


--
-- Data for Name: referrals; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.referrals (id, referrer_id, referee_id, created_at) FROM stdin;
\.


--
-- Data for Name: renewal_history; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.renewal_history (id, subscription_id, renewed_at, result, details) FROM stdin;
\.


--
-- Data for Name: reward_config; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.reward_config (id, traffic_percent, days_percent, credit_percent) FROM stdin;
1	10	10	10
\.


--
-- Data for Name: reward_effectiveness; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.reward_effectiveness (id, reward_type, total_given, total_redeemed, conversion_rate, date, created_at) FROM stdin;
\.


--
-- Data for Name: reward_history; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.reward_history (id, user_id, reward_type, reward_value, source, source_id, notes, earned_at, spent_at) FROM stdin;
\.


--
-- Data for Name: seasonal_events; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.seasonal_events (id, name, description, event_type, start_date, end_date, reward_multiplier, active, created_at) FROM stdin;
\.


--
-- Data for Name: star_history; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.star_history (id, user_id, delta, reason, source_id, notes, created_at) FROM stdin;
\.


--
-- Data for Name: star_reward_tiers; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.star_reward_tiers (id, star_threshold, title, description, reward_type, reward_value, is_active, created_at) FROM stdin;
1	3	۳ ستاره - نوآموز	۱۵٪ تخفیف برای خرید بعدی (۶۰ روز)	discount_percent	15	t	2026-05-19 16:17:17.036152
2	5	۵ ستاره - مسافر فضایی	انتخاب کنید: ۴۰,۰۰۰ تومان یا ۲۵٪ تخفیف	choice	credit:40000|discount:25	t	2026-05-19 16:17:17.04082
3	7	۷ ستاره - ناوبر	انتخاب کنید: ۱۵ روز اضافه یا ۲۰,۰۰۰ تومان	choice	days:15|credit:20000	t	2026-05-19 16:17:17.045243
4	10	۱۰ ستاره - قهرمان کهکشانی	پلن ۱۰GB رایگان + ۱۵,۰۰۰ تومان	bundle	plan:10|credit:15000	t	2026-05-19 16:17:17.048313
5	15	۱۵ ستاره - اسطوره	انتخاب کنید: پلن ۲۰GB رایگان یا ۷۵,۰۰۰ تومان	choice	plan:20|credit:75000	t	2026-05-19 16:17:17.051026
6	20	۲۰ ستاره - فرمانده کیهانی	انتخاب کنید: پلن ۴۰GB رایگان یا ۱۵۰,۰۰۰ تومان	choice	plan:40|credit:150000	t	2026-05-19 16:17:17.053581
7	30	۳۰ ستاره - امپراتور فضایی	پلن ۶۰GB رایگان + VIP (۳۰ روز) + ۳۰,۰۰۰ تومان	bundle	plan:60|vip:30|credit:30000	t	2026-05-19 16:17:17.057414
8	50	۵۰ ستاره - افسانه نهایی	پلن ۱۰۰GB رایگان + نام سفارشی + VIP مادام‌العمر + ۱۰۰,۰۰۰ تومان	bundle	plan:100|custom_name|vip:lifetime|credit:100000	t	2026-05-19 16:17:17.060869
\.


--
-- Data for Name: subscription_links; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.subscription_links (user_id, subscription_id, added_at) FROM stdin;
\.


--
-- Data for Name: subscriptions; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.subscriptions (id, user_id, referrer_id, marzban_username, sub_token, plan_name, price, status, receipt_message_id, admin_receipt_forward_message_id, admin_request_message_id, receipt_image_url, user_link_sent, low_data_notified, imminent_expiry_notified, expired_notified, created_at, renewal_paid, renewal_template, renewal_price, renewal_requested_at, renewal_applied, credit_used, applied_discount_ids, carry_over_bytes, carry_over_reset_at) FROM stdin;
1	2	\N	255255225	MjU1MjU1MjI1LDE3NzkyMTQwNjULghYqZUrdV	\N	\N	active	\N	\N	\N	\N	f	f	f	f	2026-05-19 18:07:51.058716	f	\N	\N	\N	f	0	\N	\N	\N
\.


--
-- Data for Name: ticket_messages; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.ticket_messages (id, ticket_id, sender, content_type, text, telegram_message_id, file_id, reply_to_message_id, replied_to, file_unique_id, file_name, file_size, file_mime_type, voice_duration, read_by_admin, read_by_user, created_at) FROM stdin;
\.


--
-- Data for Name: tickets; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.tickets (id, user_id, subscription_id, user_ticket_number, category, subject, status, priority, os, isp, assigned_admin_id, allow_more_from_user, notify_on_reply, hidden_from_user, hidden_at, is_private_chat, chat_invitation_sent, chat_invitation_accepted, chat_invitation_expired, chat_invitation_sent_at, chat_started_at, chat_ended_at, last_message_at, last_reminder_at, created_at, updated_at, closed_at, resolved, feedback_score, feedback_text) FROM stdin;
\.


--
-- Data for Name: user_achievements; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.user_achievements (id, user_id, achievement_id, earned_at) FROM stdin;
\.


--
-- Data for Name: user_analytics; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.user_analytics (id, user_id, date, login_count, referral_clicks, reward_redemptions, subscription_usage_bytes, created_at) FROM stdin;
1	1	2026-05-19 00:00:00	0	0	0	0	2026-05-19 19:14:14.056861
2	2	2026-05-19 00:00:00	0	0	0	0	2026-05-19 19:14:14.217165
3	1	2026-05-20 00:00:00	0	0	0	0	2026-05-20 00:14:14.018697
4	2	2026-05-20 00:00:00	0	0	0	0	2026-05-20 00:14:14.073649
\.


--
-- Data for Name: user_challenges; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.user_challenges (id, user_id, challenge_id, progress, completed, completed_at, created_at) FROM stdin;
\.


--
-- Data for Name: user_discounts; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.user_discounts (id, user_id, percent, expiration, used, source) FROM stdin;
\.


--
-- Data for Name: user_gifts; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.user_gifts (id, sender_id, receiver_id, gift_type, gift_value, plan_name, message, payment_status, payment_receipt_message_id, accepted, accepted_at, created_at) FROM stdin;
\.


--
-- Data for Name: user_star_reward_claims; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.user_star_reward_claims (id, user_id, tier_id, offered_at, expires_at, claimed_at, chosen_reward_type, status) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.users (id, chat_id, username, full_name, language, dashboard_prefs, referral_code, phone_number, created_at, stars, credit, banned, is_admin, category, level, experience_points, last_daily_login, login_streak, loyalty_points, custom_username, star_pieces, arcade_stars_this_month, arcade_stars_month_reset, show_on_leaderboard, is_vip, vip_until, discount_percent, discount_expiration) FROM stdin;
1	7115552732	Pashanimx	Ali Paşa	fa	{"lang":"fa"}	APN78X	\N	2026-05-19 16:22:59.620993	0	0	f	f	normal	1	0	\N	0	0	\N	0	0	\N	t	f	\N	0	\N
2	8148909121	Pashan1mx	Paşanim	fa	{"theme":"dark","current_sub_id":"1","welcome_shown":true}	PCXEKS	\N	2026-05-19 17:01:17.222751	0	0	f	f	normal	1	0	\N	0	0	\N	0	0	\N	t	f	\N	0	\N
\.


--
-- Data for Name: vip_orders; Type: TABLE DATA; Schema: public; Owner: astronaut_admin
--

COPY public.vip_orders (id, user_id, plan_id, days, price, receipt_image_url, status, created_at, approved_at, approved_by) FROM stdin;
\.


--
-- Name: achievements_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.achievements_id_seq', 11, true);


--
-- Name: challenges_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.challenges_id_seq', 4, true);


--
-- Name: charge_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.charge_requests_id_seq', 1, false);


--
-- Name: daily_game_plays_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.daily_game_plays_id_seq', 1, false);


--
-- Name: daily_star_caps_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.daily_star_caps_id_seq', 1, false);


--
-- Name: leaderboards_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.leaderboards_id_seq', 8, true);


--
-- Name: notifications_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.notifications_id_seq', 1, false);


--
-- Name: pending_deletion_requests_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.pending_deletion_requests_id_seq', 1, false);


--
-- Name: receipts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.receipts_id_seq', 1, false);


--
-- Name: referral_rewards_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.referral_rewards_id_seq', 1, false);


--
-- Name: referrals_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.referrals_id_seq', 1, false);


--
-- Name: renewal_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.renewal_history_id_seq', 1, false);


--
-- Name: reward_effectiveness_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.reward_effectiveness_id_seq', 1, false);


--
-- Name: reward_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.reward_history_id_seq', 1, false);


--
-- Name: seasonal_events_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.seasonal_events_id_seq', 1, false);


--
-- Name: star_history_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.star_history_id_seq', 1, false);


--
-- Name: star_reward_tiers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.star_reward_tiers_id_seq', 8, true);


--
-- Name: subscriptions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.subscriptions_id_seq', 1, true);


--
-- Name: ticket_messages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.ticket_messages_id_seq', 1, false);


--
-- Name: tickets_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.tickets_id_seq', 1, false);


--
-- Name: user_achievements_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.user_achievements_id_seq', 1, false);


--
-- Name: user_analytics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.user_analytics_id_seq', 4, true);


--
-- Name: user_challenges_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.user_challenges_id_seq', 1, false);


--
-- Name: user_discounts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.user_discounts_id_seq', 1, false);


--
-- Name: user_gifts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.user_gifts_id_seq', 1, false);


--
-- Name: user_star_reward_claims_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.user_star_reward_claims_id_seq', 1, false);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.users_id_seq', 2, true);


--
-- Name: vip_orders_id_seq; Type: SEQUENCE SET; Schema: public; Owner: astronaut_admin
--

SELECT pg_catalog.setval('public.vip_orders_id_seq', 1, false);


--
-- Name: achievements achievements_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.achievements
    ADD CONSTRAINT achievements_pkey PRIMARY KEY (id);


--
-- Name: challenges challenges_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.challenges
    ADD CONSTRAINT challenges_pkey PRIMARY KEY (id);


--
-- Name: charge_requests charge_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.charge_requests
    ADD CONSTRAINT charge_requests_pkey PRIMARY KEY (id);


--
-- Name: daily_game_plays daily_game_plays_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.daily_game_plays
    ADD CONSTRAINT daily_game_plays_pkey PRIMARY KEY (id);


--
-- Name: daily_star_caps daily_star_caps_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.daily_star_caps
    ADD CONSTRAINT daily_star_caps_pkey PRIMARY KEY (id);


--
-- Name: leaderboards leaderboards_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.leaderboards
    ADD CONSTRAINT leaderboards_pkey PRIMARY KEY (id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: pending_deletion_requests pending_deletion_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.pending_deletion_requests
    ADD CONSTRAINT pending_deletion_requests_pkey PRIMARY KEY (id);


--
-- Name: receipts receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_pkey PRIMARY KEY (id);


--
-- Name: referral_rewards referral_rewards_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.referral_rewards
    ADD CONSTRAINT referral_rewards_pkey PRIMARY KEY (id);


--
-- Name: referrals referrals_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.referrals
    ADD CONSTRAINT referrals_pkey PRIMARY KEY (id);


--
-- Name: referrals referrals_referee_id_key; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.referrals
    ADD CONSTRAINT referrals_referee_id_key UNIQUE (referee_id);


--
-- Name: renewal_history renewal_history_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.renewal_history
    ADD CONSTRAINT renewal_history_pkey PRIMARY KEY (id);


--
-- Name: reward_config reward_config_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.reward_config
    ADD CONSTRAINT reward_config_pkey PRIMARY KEY (id);


--
-- Name: reward_effectiveness reward_effectiveness_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.reward_effectiveness
    ADD CONSTRAINT reward_effectiveness_pkey PRIMARY KEY (id);


--
-- Name: reward_history reward_history_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.reward_history
    ADD CONSTRAINT reward_history_pkey PRIMARY KEY (id);


--
-- Name: seasonal_events seasonal_events_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.seasonal_events
    ADD CONSTRAINT seasonal_events_pkey PRIMARY KEY (id);


--
-- Name: star_history star_history_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.star_history
    ADD CONSTRAINT star_history_pkey PRIMARY KEY (id);


--
-- Name: star_reward_tiers star_reward_tiers_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.star_reward_tiers
    ADD CONSTRAINT star_reward_tiers_pkey PRIMARY KEY (id);


--
-- Name: star_reward_tiers star_reward_tiers_star_threshold_key; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.star_reward_tiers
    ADD CONSTRAINT star_reward_tiers_star_threshold_key UNIQUE (star_threshold);


--
-- Name: subscription_links subscription_links_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.subscription_links
    ADD CONSTRAINT subscription_links_pkey PRIMARY KEY (user_id, subscription_id);


--
-- Name: subscriptions subscriptions_marzban_username_key; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_marzban_username_key UNIQUE (marzban_username);


--
-- Name: subscriptions subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_pkey PRIMARY KEY (id);


--
-- Name: ticket_messages ticket_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.ticket_messages
    ADD CONSTRAINT ticket_messages_pkey PRIMARY KEY (id);


--
-- Name: tickets tickets_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_pkey PRIMARY KEY (id);


--
-- Name: daily_star_caps unique_user_date_cap; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.daily_star_caps
    ADD CONSTRAINT unique_user_date_cap UNIQUE (user_id, date);


--
-- Name: daily_game_plays uq_daily_play_user_date; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.daily_game_plays
    ADD CONSTRAINT uq_daily_play_user_date UNIQUE (user_id, play_date);


--
-- Name: renewal_history uq_subscription_renewed_at; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.renewal_history
    ADD CONSTRAINT uq_subscription_renewed_at UNIQUE (subscription_id, renewed_at);


--
-- Name: user_achievements user_achievements_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_achievements
    ADD CONSTRAINT user_achievements_pkey PRIMARY KEY (id);


--
-- Name: user_analytics user_analytics_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_analytics
    ADD CONSTRAINT user_analytics_pkey PRIMARY KEY (id);


--
-- Name: user_challenges user_challenges_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_challenges
    ADD CONSTRAINT user_challenges_pkey PRIMARY KEY (id);


--
-- Name: user_discounts user_discounts_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_discounts
    ADD CONSTRAINT user_discounts_pkey PRIMARY KEY (id);


--
-- Name: user_gifts user_gifts_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_gifts
    ADD CONSTRAINT user_gifts_pkey PRIMARY KEY (id);


--
-- Name: user_star_reward_claims user_star_reward_claims_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_star_reward_claims
    ADD CONSTRAINT user_star_reward_claims_pkey PRIMARY KEY (id);


--
-- Name: users users_chat_id_key; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_chat_id_key UNIQUE (chat_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_referral_code_key; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_referral_code_key UNIQUE (referral_code);


--
-- Name: vip_orders vip_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.vip_orders
    ADD CONSTRAINT vip_orders_pkey PRIMARY KEY (id);


--
-- Name: idx_achievements_requirement_type; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_achievements_requirement_type ON public.achievements USING btree (requirement_type);


--
-- Name: idx_challenges_type_active; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_challenges_type_active ON public.challenges USING btree (challenge_type, active);


--
-- Name: idx_charge_requests_status; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_charge_requests_status ON public.charge_requests USING btree (status);


--
-- Name: idx_charge_requests_user; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_charge_requests_user ON public.charge_requests USING btree (user_id);


--
-- Name: idx_leaderboards_category_period; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_leaderboards_category_period ON public.leaderboards USING btree (category, period);


--
-- Name: idx_leaderboards_date; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_leaderboards_date ON public.leaderboards USING btree (date);


--
-- Name: idx_leaderboards_score; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_leaderboards_score ON public.leaderboards USING btree (score);


--
-- Name: idx_leaderboards_user; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_leaderboards_user ON public.leaderboards USING btree (user_id);


--
-- Name: idx_notifications_created_at; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_notifications_created_at ON public.notifications USING btree (created_at);


--
-- Name: idx_notifications_user_id; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_notifications_user_id ON public.notifications USING btree (user_id);


--
-- Name: idx_notifications_user_read; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_notifications_user_read ON public.notifications USING btree (user_id, read);


--
-- Name: idx_referral_rewards_created_at; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_referral_rewards_created_at ON public.referral_rewards USING btree (created_at);


--
-- Name: idx_referral_rewards_referrer_spent; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_referral_rewards_referrer_spent ON public.referral_rewards USING btree (referrer_id, spent);


--
-- Name: idx_referral_rewards_subscription; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_referral_rewards_subscription ON public.referral_rewards USING btree (subscription_id);


--
-- Name: idx_referrals_created_at; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_referrals_created_at ON public.referrals USING btree (created_at);


--
-- Name: idx_referrals_referrer; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_referrals_referrer ON public.referrals USING btree (referrer_id);


--
-- Name: idx_renewal_history_subscription; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_renewal_history_subscription ON public.renewal_history USING btree (subscription_id);


--
-- Name: idx_reward_effectiveness_date; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_reward_effectiveness_date ON public.reward_effectiveness USING btree (date);


--
-- Name: idx_reward_effectiveness_type; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_reward_effectiveness_type ON public.reward_effectiveness USING btree (reward_type);


--
-- Name: idx_reward_history_earned_at; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_reward_history_earned_at ON public.reward_history USING btree (earned_at);


--
-- Name: idx_reward_history_source; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_reward_history_source ON public.reward_history USING btree (source);


--
-- Name: idx_reward_history_type; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_reward_history_type ON public.reward_history USING btree (reward_type);


--
-- Name: idx_reward_history_user; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_reward_history_user ON public.reward_history USING btree (user_id);


--
-- Name: idx_subscriptions_created_at; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_subscriptions_created_at ON public.subscriptions USING btree (created_at);


--
-- Name: idx_subscriptions_marzban_username; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_subscriptions_marzban_username ON public.subscriptions USING btree (marzban_username);


--
-- Name: idx_subscriptions_referrer; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_subscriptions_referrer ON public.subscriptions USING btree (referrer_id);


--
-- Name: idx_subscriptions_renewal_applied; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_subscriptions_renewal_applied ON public.subscriptions USING btree (renewal_applied);


--
-- Name: idx_subscriptions_renewal_paid; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_subscriptions_renewal_paid ON public.subscriptions USING btree (renewal_paid);


--
-- Name: idx_subscriptions_status_pending; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_subscriptions_status_pending ON public.subscriptions USING btree (status);


--
-- Name: idx_subscriptions_user_status; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_subscriptions_user_status ON public.subscriptions USING btree (user_id, status);


--
-- Name: idx_ticket_messages_created_at; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_ticket_messages_created_at ON public.ticket_messages USING btree (created_at);


--
-- Name: idx_ticket_messages_ticket_id; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_ticket_messages_ticket_id ON public.ticket_messages USING btree (ticket_id);


--
-- Name: idx_tickets_assigned_admin_id; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_tickets_assigned_admin_id ON public.tickets USING btree (assigned_admin_id);


--
-- Name: idx_tickets_category; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_tickets_category ON public.tickets USING btree (category);


--
-- Name: idx_tickets_created_at; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_tickets_created_at ON public.tickets USING btree (created_at);


--
-- Name: idx_tickets_status; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_tickets_status ON public.tickets USING btree (status);


--
-- Name: idx_tickets_user_id; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_tickets_user_id ON public.tickets USING btree (user_id);


--
-- Name: idx_user_achievements_achievement; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_user_achievements_achievement ON public.user_achievements USING btree (achievement_id);


--
-- Name: idx_user_achievements_earned_at; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_user_achievements_earned_at ON public.user_achievements USING btree (earned_at);


--
-- Name: idx_user_achievements_user; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_user_achievements_user ON public.user_achievements USING btree (user_id);


--
-- Name: idx_user_analytics_date; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_user_analytics_date ON public.user_analytics USING btree (date);


--
-- Name: idx_user_analytics_user_date; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_user_analytics_user_date ON public.user_analytics USING btree (user_id, date);


--
-- Name: idx_user_challenges_challenge; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_user_challenges_challenge ON public.user_challenges USING btree (challenge_id);


--
-- Name: idx_user_challenges_completed; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_user_challenges_completed ON public.user_challenges USING btree (completed);


--
-- Name: idx_user_challenges_user; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_user_challenges_user ON public.user_challenges USING btree (user_id);


--
-- Name: idx_user_gifts_receiver; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_user_gifts_receiver ON public.user_gifts USING btree (receiver_id);


--
-- Name: idx_user_gifts_sender; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_user_gifts_sender ON public.user_gifts USING btree (sender_id);


--
-- Name: idx_users_chat_id; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_users_chat_id ON public.users USING btree (chat_id);


--
-- Name: idx_users_created_at; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_users_created_at ON public.users USING btree (created_at);


--
-- Name: idx_users_last_daily_login; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_users_last_daily_login ON public.users USING btree (last_daily_login);


--
-- Name: idx_users_level_xp; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_users_level_xp ON public.users USING btree (level, experience_points);


--
-- Name: idx_users_login_streak; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_users_login_streak ON public.users USING btree (login_streak);


--
-- Name: idx_users_loyalty_points; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_users_loyalty_points ON public.users USING btree (loyalty_points);


--
-- Name: idx_users_referral_code; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_users_referral_code ON public.users USING btree (referral_code);


--
-- Name: idx_users_username; Type: INDEX; Schema: public; Owner: astronaut_admin
--

CREATE INDEX idx_users_username ON public.users USING btree (username);


--
-- Name: charge_requests charge_requests_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.charge_requests
    ADD CONSTRAINT charge_requests_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscriptions(id);


--
-- Name: charge_requests charge_requests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.charge_requests
    ADD CONSTRAINT charge_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: daily_game_plays daily_game_plays_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.daily_game_plays
    ADD CONSTRAINT daily_game_plays_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: daily_star_caps daily_star_caps_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.daily_star_caps
    ADD CONSTRAINT daily_star_caps_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: leaderboards leaderboards_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.leaderboards
    ADD CONSTRAINT leaderboards_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: notifications notifications_ticket_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_ticket_id_fkey FOREIGN KEY (ticket_id) REFERENCES public.tickets(id);


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: pending_deletion_requests pending_deletion_requests_processed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.pending_deletion_requests
    ADD CONSTRAINT pending_deletion_requests_processed_by_fkey FOREIGN KEY (processed_by) REFERENCES public.users(id);


--
-- Name: pending_deletion_requests pending_deletion_requests_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.pending_deletion_requests
    ADD CONSTRAINT pending_deletion_requests_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscriptions(id);


--
-- Name: pending_deletion_requests pending_deletion_requests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.pending_deletion_requests
    ADD CONSTRAINT pending_deletion_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: receipts receipts_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscriptions(id);


--
-- Name: receipts receipts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: referral_rewards referral_rewards_referrer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.referral_rewards
    ADD CONSTRAINT referral_rewards_referrer_id_fkey FOREIGN KEY (referrer_id) REFERENCES public.users(id);


--
-- Name: referral_rewards referral_rewards_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.referral_rewards
    ADD CONSTRAINT referral_rewards_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscriptions(id);


--
-- Name: referrals referrals_referee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.referrals
    ADD CONSTRAINT referrals_referee_id_fkey FOREIGN KEY (referee_id) REFERENCES public.users(id);


--
-- Name: referrals referrals_referrer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.referrals
    ADD CONSTRAINT referrals_referrer_id_fkey FOREIGN KEY (referrer_id) REFERENCES public.users(id);


--
-- Name: renewal_history renewal_history_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.renewal_history
    ADD CONSTRAINT renewal_history_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscriptions(id);


--
-- Name: reward_history reward_history_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.reward_history
    ADD CONSTRAINT reward_history_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: star_history star_history_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.star_history
    ADD CONSTRAINT star_history_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: subscription_links subscription_links_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.subscription_links
    ADD CONSTRAINT subscription_links_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscriptions(id);


--
-- Name: subscription_links subscription_links_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.subscription_links
    ADD CONSTRAINT subscription_links_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: subscriptions subscriptions_referrer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_referrer_id_fkey FOREIGN KEY (referrer_id) REFERENCES public.users(id);


--
-- Name: subscriptions subscriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ticket_messages ticket_messages_replied_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.ticket_messages
    ADD CONSTRAINT ticket_messages_replied_to_fkey FOREIGN KEY (replied_to) REFERENCES public.ticket_messages(id);


--
-- Name: ticket_messages ticket_messages_ticket_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.ticket_messages
    ADD CONSTRAINT ticket_messages_ticket_id_fkey FOREIGN KEY (ticket_id) REFERENCES public.tickets(id);


--
-- Name: tickets tickets_assigned_admin_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_assigned_admin_id_fkey FOREIGN KEY (assigned_admin_id) REFERENCES public.users(id);


--
-- Name: tickets tickets_subscription_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES public.subscriptions(id);


--
-- Name: tickets tickets_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.tickets
    ADD CONSTRAINT tickets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_achievements user_achievements_achievement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_achievements
    ADD CONSTRAINT user_achievements_achievement_id_fkey FOREIGN KEY (achievement_id) REFERENCES public.achievements(id);


--
-- Name: user_achievements user_achievements_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_achievements
    ADD CONSTRAINT user_achievements_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_analytics user_analytics_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_analytics
    ADD CONSTRAINT user_analytics_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_challenges user_challenges_challenge_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_challenges
    ADD CONSTRAINT user_challenges_challenge_id_fkey FOREIGN KEY (challenge_id) REFERENCES public.challenges(id);


--
-- Name: user_challenges user_challenges_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_challenges
    ADD CONSTRAINT user_challenges_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_discounts user_discounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_discounts
    ADD CONSTRAINT user_discounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_gifts user_gifts_receiver_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_gifts
    ADD CONSTRAINT user_gifts_receiver_id_fkey FOREIGN KEY (receiver_id) REFERENCES public.users(id);


--
-- Name: user_gifts user_gifts_sender_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_gifts
    ADD CONSTRAINT user_gifts_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.users(id);


--
-- Name: user_star_reward_claims user_star_reward_claims_tier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_star_reward_claims
    ADD CONSTRAINT user_star_reward_claims_tier_id_fkey FOREIGN KEY (tier_id) REFERENCES public.star_reward_tiers(id);


--
-- Name: user_star_reward_claims user_star_reward_claims_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.user_star_reward_claims
    ADD CONSTRAINT user_star_reward_claims_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: vip_orders vip_orders_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: astronaut_admin
--

ALTER TABLE ONLY public.vip_orders
    ADD CONSTRAINT vip_orders_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--

\unrestrict w91lJThbRRcncfhs4gNjALoqIGkAEbquHTC7wxmGa5cyIlyy8YDZ6DxYh3zcl4D

