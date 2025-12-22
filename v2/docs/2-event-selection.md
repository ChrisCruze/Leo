# Event Selection Pipeline - Step 2

## Overview

This document describes the event selection pipeline that filters events based on qualification criteria for messaging campaigns. The pipeline identifies which events are qualified for promotion by filtering for future events, public events, and events with available capacity.

## Event Schema (from MongoDB)

The `events.json` file contains event data from MongoDB with the following schema:

### Core Identity Fields
- `_id` (string): MongoDB ObjectId as string
- `id` (string): Event identifier (typically same as `_id`)
- `name` (string): Event name
- `email` (string): Contact email for the event
- `phone` (string): Contact phone for the event

### Date & Time Fields
- `startDate` (string): Event start date/time in ISO 8601 format with 'Z' timezone (e.g., "2019-08-05T17:00:00.000Z")
- `endDate` (string): Event end date/time in ISO 8601 format with 'Z' timezone
- `createdAt` (string): Event creation date in ISO 8601 format

### Event Type & Status Fields
- `type` (string): Event type - "public" or "private"
- `eventStatus` (string): Event approval status (e.g., "approved", "canceled", "pending")
- `active` (boolean): Whether event is active
- `status` (number): Status code (2 = active)
- `lifecycle` (object): Lifecycle information with status and update history

### Participant Fields
- `maxParticipants` (number): Maximum number of participants allowed
- `minParticipants` (number): Minimum number of participants required
- `participants` (array): List of participant identifiers (user IDs or emails)
- `ownerId` (string): Event owner/creator user ID
- `invitedParticipants` (array, optional): List of invited participant identifiers

### Venue Fields
- `venueId` (string): Venue identifier
- `venueName` (string): Name of the venue
- `venueImage` (string, nullable): URL to venue image
- `neighborhood` (string): Event neighborhood location

### Content Fields
- `description` (string, nullable): Event description (may contain HTML)
- `categories` (array, nullable): Event categories (e.g., ["CUBAN", "MEDITERRANEAN"])
- `features` (array, nullable): Event features (e.g., ["groups", "live-music"])
- `notes` (string, nullable): Additional notes

### Payment & Configuration Fields
- `paymentConfig` (object): Payment configuration
- `entranceFee` (number, nullable): Entrance fee amount
- `orders` (array): List of orders associated with the event

### Additional Fields
- `chatReference` (string): Chat reference ID
- `needsVenueReapproval` (boolean): Whether venue needs reapproval

## Filtering Criteria

Events must meet the following criteria to be qualified for messaging campaigns:

### Required Criteria

1. **Future Events**
   - **Field**: `startDate`
   - **Requirement**: Event start date must be in the future (after current date/time)
   - **Format**: ISO 8601 with 'Z' timezone (e.g., "2019-08-05T17:00:00.000Z")
   - **Usage**: Only future events are relevant for promotion

2. **Public Events**
   - **Field**: `type`
   - **Requirement**: Must be "public" (not "private")
   - **Usage**: Only public events can be promoted to users

3. **Active Events (Not Canceled)**
   - **Field**: `eventStatus`
   - **Requirement**: Must not be "canceled"
   - **Usage**: Canceled events should not be promoted to users

4. **Events with Available Capacity**
   - **Fields**: `participants` (array) and `maxParticipants` (number)
   - **Requirement**: `len(participants) < maxParticipants`
   - **Usage**: Only events with available spots are worth promoting

### Filtering Logic

The pipeline applies four levels of filtering:

1. **Future Events Filter**: Events whose `startDate` is after the current date/time are kept. Events with missing or invalid `startDate` are filtered out.

2. **Public Events Filter**: Events where `type == "public"` are kept. Events where `type` is "private" or missing are filtered out.

3. **Active Events Filter**: Events where `eventStatus` is not "canceled" are kept. Events with `eventStatus == "canceled"` are filtered out.

4. **Capacity Filter**: Events where the number of participants (length of `participants` array) is less than `maxParticipants` are kept. Events that are at or over capacity, or missing required fields, are filtered out.

## Results

*Results from pipeline execution on 2025-12-21 20:42:35*

### Filtering Statistics

- **Total events loaded**: 4,871
- **Events filtered out (past events)**: 4,860
- **Events filtered out (private events)**: 1
- **Events filtered out (no capacity)**: 1
- **Final qualified events**: 9

### Qualified Events List

The following 9 events qualified for messaging campaigns:

1. **Holiday Karaoke**
   - Date: Dec 28, 2025 at 10:00 PM
   - Participants: 9/10

2. **✨ Year-End Girls Dine Out ✨**
   - Date: Dec 26, 2025 at 11:30 PM
   - Participants: 2/10

3. **Kicking off 2026: Lunch at Jake's Steakhouse**
   - Date: Jan 11, 2026 at 08:00 PM
   - Participants: 6/10

4. **Beginner Salsa Lesson - January 17th**
   - Date: Jan 17, 2026 at 05:00 PM
   - Participants: 1/8

5. **Mexican Brunch 🇲🇽**
   - Date: Dec 28, 2025 at 06:00 PM
   - Participants: 6/7

6. **WKDVBS NYE PARTY!!!**
   - Date: Jan 01, 2026 at 02:00 AM
   - Participants: 6/10

7. **A Cozy Christmas Dinner 🌟**
   - Date: Dec 25, 2025 at 11:30 PM
   - Participants: 3/10

8. **NYE Dinner + Midnight Champagne Toast 🥂✨**
   - Date: Jan 01, 2026 at 12:00 AM
   - Participants: 8/10

9. **Test**
   - Date: Dec 22, 2025 at 08:30 PM
   - Participants: 1/2

### Analysis

The pipeline results reveal important insights about the event database:

1. **Most Events are Historical**: Out of 4,871 total events, 4,860 (99.8%) are past events. This indicates the database contains primarily historical event data.

2. **High Public Event Rate**: Of the 11 future events, 10 (90.9%) are public events. Only 1 private event was found among future events.

3. **Good Capacity Availability**: Of the 10 public future events, 9 (90%) have available capacity. Only 1 event was at full capacity.

4. **Event Distribution**:
   - **Holiday/Seasonal Events**: 5 events (Christmas, NYE, Year-End)
   - **Regular Events**: 4 events (Karaoke, Salsa, Brunch, Test)

5. **Capacity Utilization**:
   - Most events have moderate to high capacity utilization (6-9 participants)
   - Several events have low utilization (1-3 participants), indicating good opportunities for promotion
   - "Holiday Karaoke" is nearly full (9/10) but still has 1 spot available

6. **Key Insights**:
   - The filtering pipeline successfully identified 9 qualified events from a large historical dataset
   - All qualified events are within the next few weeks, making them timely for promotion
   - The low number of qualified events (9 out of 4,871) suggests the need for ongoing event creation to maintain a healthy pipeline

