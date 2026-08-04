-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.scans (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  scan_id character varying NOT NULL UNIQUE,
  hwid character varying NOT NULL,
  timestamp timestamp with time zone NOT NULL DEFAULT timezone('utc'::text, now()),
  system_info jsonb NOT NULL,
  disk_performance jsonb NOT NULL,
  stats jsonb NOT NULL,
  risk_summary jsonb NOT NULL,
  applications jsonb DEFAULT '[]'::jsonb,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  server_key character varying DEFAULT 'default'::character varying,
  pin_code character varying,
  created_by_discord_id character varying,
  created_by_username character varying,
  CONSTRAINT scans_pkey PRIMARY KEY (id)
);
CREATE TABLE public.admins (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  discord_id character varying NOT NULL,
  discord_username character varying,
  discord_avatar character varying,
  role character varying NOT NULL DEFAULT 'admin'::character varying,
  created_at timestamp with time zone DEFAULT now(),
  server_key character varying,
  email character varying,
  last_login_at timestamp with time zone,
  created_by_discord_id character varying,
  server_name character varying DEFAULT 'Serveur Général'::character varying,
  CONSTRAINT admins_pkey PRIMARY KEY (id)
);
CREATE TABLE public.servers (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  server_key character varying NOT NULL UNIQUE,
  name character varying NOT NULL,
  owner_discord_id character varying,
  created_at timestamp with time zone DEFAULT now(),
  server_prefix character varying,
  owner_name character varying,
  max_pins_quota integer DEFAULT 0,
  status character varying DEFAULT 'PENDING'::character varying,
  invite_url character varying,
  subscription_expires_at timestamp with time zone,
  icon text,
  CONSTRAINT servers_pkey PRIMARY KEY (id)
);
CREATE TABLE public.scan_pins (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  pin_code character varying NOT NULL UNIQUE,
  created_by_discord_id character varying NOT NULL,
  created_by_username character varying,
  server_key character varying NOT NULL DEFAULT 'default'::character varying,
  status character varying NOT NULL DEFAULT 'PENDING'::character varying,
  created_at timestamp with time zone DEFAULT now(),
  expires_at timestamp with time zone NOT NULL,
  used_at timestamp with time zone,
  used_hwid character varying,
  CONSTRAINT scan_pins_pkey PRIMARY KEY (id)
);
CREATE TABLE public.discord_profiles (
  discord_id character varying NOT NULL,
  username character varying NOT NULL,
  avatar_url character varying,
  email character varying,
  last_login_at timestamp with time zone DEFAULT now(),
  user_guilds jsonb DEFAULT '[]'::jsonb,
  CONSTRAINT discord_profiles_pkey PRIMARY KEY (discord_id)
);
CREATE TABLE public.agents (
  id bigint NOT NULL DEFAULT nextval('agents_id_seq'::regclass),
  device_id text NOT NULL UNIQUE,
  hostname text,
  username text,
  os_version text,
  architecture text,
  local_ip text,
  agent_version text,
  status text DEFAULT 'OFFLINE'::text,
  cpu_percent real DEFAULT 0,
  ram_used_percent real DEFAULT 0,
  last_seen timestamp with time zone,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT agents_pkey PRIMARY KEY (id)
);
CREATE TABLE public.agent_commands (
  id bigint NOT NULL DEFAULT nextval('agent_commands_id_seq'::regclass),
  device_id text NOT NULL,
  command_type text NOT NULL,
  command_content text,
  status text DEFAULT 'PENDING'::text,
  result text,
  created_at timestamp with time zone DEFAULT now(),
  completed_at timestamp with time zone,
  CONSTRAINT agent_commands_pkey PRIMARY KEY (id)
);