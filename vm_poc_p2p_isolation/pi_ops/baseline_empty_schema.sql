-- MySQL dump 10.13  Distrib 8.0.46, for Linux (aarch64)
--
-- Host: localhost    Database: devicemanagement
-- ------------------------------------------------------
-- Server version	8.0.46

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `audit_logs`
--

DROP TABLE IF EXISTS `audit_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `audit_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `command_id` varchar(191) DEFAULT NULL,
  `user_id` varchar(191) DEFAULT NULL,
  `u_id` int DEFAULT NULL,
  `actor_id` varchar(191) DEFAULT NULL,
  `actor_type` varchar(32) DEFAULT NULL,
  `device_id` varchar(191) DEFAULT NULL,
  `family_id` int DEFAULT NULL,
  `action` varchar(64) DEFAULT NULL,
  `parameters` json DEFAULT NULL,
  `raw_data` json DEFAULT NULL,
  `status` varchar(32) DEFAULT NULL,
  `decision` varchar(32) DEFAULT NULL,
  `reason` varchar(255) DEFAULT NULL,
  `prev_hash` char(64) DEFAULT NULL,
  `current_hash` char(64) DEFAULT NULL,
  `hash` char(64) DEFAULT NULL,
  `timestamp` bigint DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_device` (`device_id`),
  KEY `idx_family` (`family_id`),
  KEY `idx_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `audit_logs`
--

LOCK TABLES `audit_logs` WRITE;
/*!40000 ALTER TABLE `audit_logs` DISABLE KEYS */;
/*!40000 ALTER TABLE `audit_logs` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `control_commands`
--

DROP TABLE IF EXISTS `control_commands`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `control_commands` (
  `command_id` varchar(191) NOT NULL,
  `family_id` int NOT NULL,
  `device_id` varchar(191) NOT NULL,
  `actor_id` varchar(191) DEFAULT NULL,
  `actor_type` varchar(32) DEFAULT NULL,
  `action` varchar(32) DEFAULT NULL,
  `parameters` json DEFAULT NULL,
  `control_mode` varchar(16) DEFAULT NULL,
  `target_topic` varchar(255) DEFAULT NULL,
  `request_payload` json DEFAULT NULL,
  `response_payload` json DEFAULT NULL,
  `status` varchar(32) DEFAULT NULL,
  `reason` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `published_at` datetime DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`command_id`),
  KEY `idx_device` (`device_id`),
  KEY `idx_family` (`family_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `control_commands`
--

LOCK TABLES `control_commands` WRITE;
/*!40000 ALTER TABLE `control_commands` DISABLE KEYS */;
/*!40000 ALTER TABLE `control_commands` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `device_credentials`
--

DROP TABLE IF EXISTS `device_credentials`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `device_credentials` (
  `credential_id` varchar(191) NOT NULL,
  `device_id` varchar(191) NOT NULL,
  `family_id` int DEFAULT NULL,
  `gateway_id` varchar(191) DEFAULT NULL,
  `credential_type` varchar(64) NOT NULL DEFAULT 'ECDH_DEVICE_PUBLIC_KEY',
  `public_key_hash` char(64) NOT NULL,
  `status` varchar(32) NOT NULL DEFAULT 'Active',
  `issued_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `revoked_at` datetime DEFAULT NULL,
  `revoked_by` varchar(191) DEFAULT NULL,
  `revocation_reason` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`credential_id`),
  KEY `idx_device_credential_device` (`device_id`,`status`),
  KEY `idx_device_credential_family` (`family_id`),
  KEY `idx_device_credential_gateway` (`gateway_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `device_credentials`
--

LOCK TABLES `device_credentials` WRITE;
/*!40000 ALTER TABLE `device_credentials` DISABLE KEYS */;
/*!40000 ALTER TABLE `device_credentials` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `device_telemetry`
--

DROP TABLE IF EXISTS `device_telemetry`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `device_telemetry` (
  `id` int NOT NULL AUTO_INCREMENT,
  `family_id` int DEFAULT NULL,
  `device_id` varchar(191) NOT NULL,
  `command_id` varchar(191) DEFAULT NULL,
  `physical_state` varchar(32) DEFAULT NULL,
  `status` varchar(32) DEFAULT NULL,
  `telemetry_data` json DEFAULT NULL,
  `battery` int DEFAULT NULL,
  `rssi` int DEFAULT NULL,
  `raw_data` json DEFAULT NULL,
  `recorded_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_device_time` (`device_id`,`recorded_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `device_telemetry`
--

LOCK TABLES `device_telemetry` WRITE;
/*!40000 ALTER TABLE `device_telemetry` DISABLE KEYS */;
/*!40000 ALTER TABLE `device_telemetry` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `devices`
--

DROP TABLE IF EXISTS `devices`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `devices` (
  `device_id` varchar(191) NOT NULL,
  `device_type` varchar(64) NOT NULL,
  `device_name` varchar(191) DEFAULT NULL,
  `status` varchar(32) NOT NULL DEFAULT 'Active',
  `last_action` varchar(64) DEFAULT NULL,
  `family_id` int DEFAULT NULL,
  `gateway_id` varchar(191) DEFAULT NULL,
  `owner_user_id` varchar(191) DEFAULT NULL,
  `device_public_key` text,
  `gateway_public_key` text,
  `session_key_hash` varchar(191) DEFAULT NULL,
  `pairing_status` varchar(32) DEFAULT NULL,
  `paired_at` datetime DEFAULT NULL,
  `revoked_at` datetime DEFAULT NULL,
  `revoked_by` varchar(191) DEFAULT NULL,
  `revocation_reason` varchar(255) DEFAULT NULL,
  `physical_state` varchar(32) DEFAULT NULL,
  `battery` int DEFAULT NULL,
  `rssi` int DEFAULT NULL,
  `online_status` varchar(32) DEFAULT NULL,
  `last_command` varchar(64) DEFAULT NULL,
  `last_seen` datetime DEFAULT NULL,
  `last_update` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  `maintenance_mode` tinyint(1) NOT NULL DEFAULT '0',
  `maintenance_expires_at` datetime DEFAULT NULL,
  `maintenance_reason` varchar(255) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`device_id`),
  KEY `idx_family` (`family_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `devices`
--

LOCK TABLES `devices` WRITE;
/*!40000 ALTER TABLE `devices` DISABLE KEYS */;
/*!40000 ALTER TABLE `devices` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `families`
--

DROP TABLE IF EXISTS `families`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `families` (
  `id` int NOT NULL AUTO_INCREMENT,
  `family_name` varchar(191) NOT NULL,
  `admin_uid` varchar(191) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `families`
--

LOCK TABLES `families` WRITE;
/*!40000 ALTER TABLE `families` DISABLE KEYS */;
/*!40000 ALTER TABLE `families` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `family_invitations`
--

DROP TABLE IF EXISTS `family_invitations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `family_invitations` (
  `id` int NOT NULL AUTO_INCREMENT,
  `family_id` int NOT NULL,
  `inviter_uid` varchar(191) NOT NULL,
  `invitee_uid` varchar(191) NOT NULL,
  `role` varchar(32) NOT NULL DEFAULT 'Guest',
  `status` varchar(32) NOT NULL DEFAULT 'Pending',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_invitee` (`invitee_uid`),
  KEY `idx_family` (`family_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `family_invitations`
--

LOCK TABLES `family_invitations` WRITE;
/*!40000 ALTER TABLE `family_invitations` DISABLE KEYS */;
/*!40000 ALTER TABLE `family_invitations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `gateway_trust_links`
--

DROP TABLE IF EXISTS `gateway_trust_links`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `gateway_trust_links` (
  `link_id` varchar(191) NOT NULL,
  `gateway_a_id` varchar(191) NOT NULL,
  `gateway_b_id` varchar(191) NOT NULL,
  `created_by` varchar(191) NOT NULL,
  `status` varchar(32) NOT NULL DEFAULT 'PENDING',
  `pairing_token_hash` char(64) DEFAULT NULL,
  `expires_at` datetime DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `confirmed_at` datetime DEFAULT NULL,
  `revoked_at` datetime DEFAULT NULL,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`link_id`),
  UNIQUE KEY `uq_gateway_trust_pair` (`gateway_a_id`,`gateway_b_id`),
  UNIQUE KEY `uq_gateway_trust_token_hash` (`pairing_token_hash`),
  KEY `idx_gateway_trust_status` (`status`),
  KEY `idx_gateway_trust_expires` (`expires_at`),
  KEY `idx_gateway_trust_created_by` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `gateway_trust_links`
--

LOCK TABLES `gateway_trust_links` WRITE;
/*!40000 ALTER TABLE `gateway_trust_links` DISABLE KEYS */;
/*!40000 ALTER TABLE `gateway_trust_links` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `gateways`
--

DROP TABLE IF EXISTS `gateways`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `gateways` (
  `gateway_id` varchar(191) NOT NULL,
  `family_id` int NOT NULL,
  `owner_user_id` varchar(191) NOT NULL,
  `gateway_name` varchar(191) NOT NULL DEFAULT 'æœªå‘½å Gateway',
  `status` varchar(32) NOT NULL DEFAULT 'Active',
  `public_key` text,
  `public_key_fingerprint` char(64) DEFAULT NULL,
  `hardware_model` varchar(100) DEFAULT NULL,
  `firmware_version` varchar(100) DEFAULT NULL,
  `binding_method` varchar(64) DEFAULT NULL,
  `initialized_at` datetime DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `last_seen_at` datetime DEFAULT NULL,
  PRIMARY KEY (`gateway_id`),
  UNIQUE KEY `uq_gateway_public_key_fingerprint` (`public_key_fingerprint`),
  KEY `idx_gateway_family` (`family_id`),
  KEY `idx_gateway_owner` (`owner_user_id`),
  KEY `idx_gateway_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `gateways`
--

LOCK TABLES `gateways` WRITE;
/*!40000 ALTER TABLE `gateways` DISABLE KEYS */;
/*!40000 ALTER TABLE `gateways` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guest_tokens`
--

DROP TABLE IF EXISTS `guest_tokens`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guest_tokens` (
  `token_id` varchar(191) NOT NULL,
  `token_hash` char(64) NOT NULL,
  `family_id` int NOT NULL,
  `device_id` varchar(191) DEFAULT NULL,
  `allowed_actions` json DEFAULT NULL,
  `expires_at` datetime NOT NULL,
  `used_count` int NOT NULL DEFAULT '0',
  `max_uses` int NOT NULL DEFAULT '1',
  `revoked` tinyint(1) NOT NULL DEFAULT '0',
  `revoked_at` datetime DEFAULT NULL,
  `revoked_by` varchar(191) DEFAULT NULL,
  `revocation_reason_code` varchar(64) DEFAULT NULL,
  `revocation_reason_hash` char(64) DEFAULT NULL,
  `created_by` varchar(191) DEFAULT NULL,
  `last_used_at` datetime DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`token_id`),
  KEY `idx_family` (`family_id`),
  KEY `idx_token_hash` (`token_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guest_tokens`
--

LOCK TABLES `guest_tokens` WRITE;
/*!40000 ALTER TABLE `guest_tokens` DISABLE KEYS */;
/*!40000 ALTER TABLE `guest_tokens` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ledger_bridge_receipts`
--

DROP TABLE IF EXISTS `ledger_bridge_receipts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ledger_bridge_receipts` (
  `event_id` varchar(191) NOT NULL,
  `claim_token` char(64) NOT NULL,
  `action` varchar(16) NOT NULL,
  `request_hash` char(64) NOT NULL,
  `response` json NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`event_id`,`claim_token`,`action`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ledger_bridge_receipts`
--

LOCK TABLES `ledger_bridge_receipts` WRITE;
/*!40000 ALTER TABLE `ledger_bridge_receipts` DISABLE KEYS */;
/*!40000 ALTER TABLE `ledger_bridge_receipts` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `ledger_events`
--

DROP TABLE IF EXISTS `ledger_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ledger_events` (
  `event_id` varchar(191) NOT NULL,
  `dedup_key` varchar(191) NOT NULL,
  `uc_id` varchar(32) NOT NULL,
  `event_type` varchar(191) NOT NULL,
  `family_id` int DEFAULT NULL,
  `gateway_id` varchar(191) DEFAULT NULL,
  `device_id` varchar(191) DEFAULT NULL,
  `created_by` varchar(191) DEFAULT NULL,
  `payload` json NOT NULL,
  `payload_hash` char(64) NOT NULL,
  `status` varchar(32) NOT NULL DEFAULT 'PENDING',
  `ledger_reference` varchar(255) DEFAULT NULL,
  `retry_count` int NOT NULL DEFAULT '0',
  `last_error` text,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `submitted_at` datetime DEFAULT NULL,
  `confirmed_at` datetime DEFAULT NULL,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `worker_id` varchar(128) DEFAULT NULL,
  `claim_token` char(64) DEFAULT NULL,
  `lease_until` datetime(6) DEFAULT NULL,
  `next_retry_at` datetime(6) DEFAULT NULL,
  `confirmation_method` varchar(128) DEFAULT NULL,
  PRIMARY KEY (`event_id`),
  UNIQUE KEY `uq_ledger_dedup_key` (`dedup_key`),
  KEY `idx_ledger_status_created` (`status`,`created_at`),
  KEY `idx_ledger_family` (`family_id`,`created_at`),
  KEY `idx_ledger_gateway` (`gateway_id`,`created_at`),
  KEY `idx_ledger_device` (`device_id`,`created_at`),
  KEY `idx_ledger_event_type` (`event_type`,`created_at`),
  KEY `idx_ledger_bridge_queue` (`status`,`next_retry_at`,`lease_until`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `ledger_events`
--

LOCK TABLES `ledger_events` WRITE;
/*!40000 ALTER TABLE `ledger_events` DISABLE KEYS */;
/*!40000 ALTER TABLE `ledger_events` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `physical_override_events`
--

DROP TABLE IF EXISTS `physical_override_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `physical_override_events` (
  `event_id` varchar(191) NOT NULL,
  `idempotency_key` varchar(191) NOT NULL,
  `family_id` int NOT NULL,
  `gateway_id` varchar(191) NOT NULL,
  `device_id` varchar(191) NOT NULL,
  `local_sequence` bigint NOT NULL,
  `event_timestamp` datetime NOT NULL,
  `received_at` datetime NOT NULL,
  `action` varchar(64) DEFAULT NULL,
  `previous_state` varchar(32) DEFAULT NULL,
  `new_state` varchar(32) DEFAULT NULL,
  `source_payload_hash` char(64) NOT NULL,
  `signer_key_id` varchar(191) NOT NULL,
  `signature` text NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`event_id`),
  UNIQUE KEY `idempotency_key` (`idempotency_key`),
  UNIQUE KEY `uq_override_sequence` (`gateway_id`,`device_id`,`local_sequence`),
  KEY `idx_override_family_time` (`family_id`,`event_timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `physical_override_events`
--

LOCK TABLES `physical_override_events` WRITE;
/*!40000 ALTER TABLE `physical_override_events` DISABLE KEYS */;
/*!40000 ALTER TABLE `physical_override_events` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `policy_rules`
--

DROP TABLE IF EXISTS `policy_rules`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `policy_rules` (
  `id` int NOT NULL AUTO_INCREMENT,
  `family_id` int NOT NULL,
  `device_id` varchar(191) DEFAULT NULL,
  `role` varchar(32) DEFAULT NULL,
  `action` varchar(32) DEFAULT NULL,
  `effect` varchar(16) NOT NULL DEFAULT 'allow',
  `enabled` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_family` (`family_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `policy_rules`
--

LOCK TABLES `policy_rules` WRITE;
/*!40000 ALTER TABLE `policy_rules` DISABLE KEYS */;
/*!40000 ALTER TABLE `policy_rules` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `security_events`
--

DROP TABLE IF EXISTS `security_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `security_events` (
  `security_event_id` varchar(191) NOT NULL,
  `dedup_key` varchar(191) NOT NULL,
  `family_id` int NOT NULL,
  `gateway_id` varchar(191) DEFAULT NULL,
  `device_id` varchar(191) DEFAULT NULL,
  `request_id` varchar(191) DEFAULT NULL,
  `anomaly_type` varchar(64) NOT NULL,
  `severity` varchar(16) NOT NULL,
  `detected_by` varchar(64) DEFAULT NULL,
  `reason_code` varchar(64) DEFAULT NULL,
  `evidence_hash` char(64) DEFAULT NULL,
  `occurred_at` datetime NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`security_event_id`),
  UNIQUE KEY `dedup_key` (`dedup_key`),
  KEY `idx_security_family_time` (`family_id`,`occurred_at`),
  KEY `idx_security_type_time` (`anomaly_type`,`occurred_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `security_events`
--

LOCK TABLES `security_events` WRITE;
/*!40000 ALTER TABLE `security_events` DISABLE KEYS */;
/*!40000 ALTER TABLE `security_events` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `user_families`
--

DROP TABLE IF EXISTS `user_families`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_families` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` varchar(191) NOT NULL,
  `family_id` int NOT NULL,
  `role` varchar(32) NOT NULL DEFAULT 'Member',
  `status` varchar(32) DEFAULT NULL,
  `start_time` datetime DEFAULT NULL,
  `end_time` datetime DEFAULT NULL,
  `max_uses` int DEFAULT NULL,
  `guest_grant_id` varchar(191) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_family` (`user_id`,`family_id`),
  KEY `idx_family` (`family_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `user_families`
--

LOCK TABLES `user_families` WRITE;
/*!40000 ALTER TABLE `user_families` DISABLE KEYS */;
/*!40000 ALTER TABLE `user_families` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` varchar(191) NOT NULL,
  `username` varchar(191) NOT NULL,
  `email` varchar(191) DEFAULT NULL,
  `phone_number` varchar(32) DEFAULT NULL,
  `password_hash` varchar(255) NOT NULL,
  `status` varchar(32) NOT NULL DEFAULT 'Active',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-10-24 10:56:17
