# Fill The Table Campaign

An intelligent campaign system that matches highly engaged users with underfilled events to increase participation.

## Overview

This campaign identifies:
- **Top Users**: Users who have attended the most events and have complete profiles
- **Underfilled Events**: Public events with less than 50% participation

The system uses AI to intelligently match users to events based on interests, location, and engagement history.

## Features

- **MongoDB Integration**: Fetches user and event data from MongoDB
- **Firebase Persistence**: Saves all campaign data (prompts, matches, messages, reports) to Firebase
- **AI-Powered Matching**: Uses Claude (Anthropic) to match users to events with personalized reasoning
- **Summary Generation**: Creates summaries for users and events to enable better matching
- **Personalized Messages**: Generates custom invitation messages for each user-event match
- **Comprehensive Logging**: Detailed logs of all operations
- **Final Reporting**: Generates and saves detailed campaign reports

## Configuration

Set the following environment variables:

```bash
# MongoDB
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB=cuculi

# Firebase
FIREBASE_CREDENTIALS_PATH=path/to/firebase-credentials.json
FIREBASE_DB_URL=https://your-project.firebaseio.com

# Anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key
```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python fill_the_table.py
```

## Data Structure

### MongoDB Collections

#### User Object Schema

Example user object from MongoDB:

```json
{
  "_id": "5d472387cc6e3963a965a7b7",
  "firstName": "Yuka",
  "lastName": "Kiso",
  "email": "yuka.kiso@gmail.com",
  "phone": "+16467892387",
  "gender": "female",
  "homeNeighborhood": "midtown-east",
  "interests": ["movies", "sports", "travel", "eatingOut"],
  "occupation": "Tech Founder",
  "birthDay": "1990-04-12T04:00:00.000Z",
  "createdAt": "2019-08-04T18:27:19.502Z",
  "role": "AMBASSADOR",
  "status": 2,
  "active": true
}
```

**Key User Fields:**
- `_id` / `id`: User ID (ObjectId as string)
- `firstName`, `lastName`: User's name
- `email`: User email address
- `phone`: User phone number
- `gender`: User gender
- `homeNeighborhood`: User's neighborhood (e.g., "midtown-east", "hells-kitchen")
- `interests`: Array of interest strings (e.g., ["art", "music", "eatingOut"])
- `occupation`: User's occupation
- `birthDay`: Date of birth (ISO string)
- `createdAt`: Account creation date (ISO string)
- `role`: User role (e.g., "REGULAR", "AMBASSADOR")
- `status`: Status code (2 = active)
- `active`: Boolean indicating if account is active

**Note:** Users do NOT have an `eventsAttended` field. Event participation is determined by checking if the user's ID is in the event's `participants` array or if they are the event's `ownerId`.

#### Event Object Schema

Example event object from MongoDB:

```json
{
  "_id": "5e331b72fef9de056e5b6113",
  "name": "Cuban night 🇨🇺🇨🇺",
  "startDate": "2020-02-01T00:00:00.687Z",
  "endDate": "2020-02-01T04:59:59.999Z",
  "type": "public",
  "maxParticipants": 4,
  "minParticipants": 0,
  "participants": [
    "tiffany.beneke@gmail.com",
    "ayatanaka2019@gmail.com",
    "pejack0192@gmail.com"
  ],
  "neighborhood": "greenwich-village",
  "venueName": "Cuba Restaurant and Rum Bar",
  "venueId": "5e30b4c6fef9de056e5b60df",
  "categories": ["CUBAN"],
  "features": null,
  "ownerId": "5d404e532cf5f83a3dbcf292",
  "description": "...",
  "eventStatus": "approved",
  "active": true
}
```

**Key Event Fields:**
- `_id` / `id`: Event ID (ObjectId as string)
- `name`: Event name (NOT `title`)
- `startDate`: Event start date/time (ISO string, NOT `date`)
- `endDate`: Event end date/time (ISO string)
- `type`: Event type - **"public"** or **"private"** (NOT `isPublic` boolean)
- `maxParticipants`: Maximum number of participants (NOT `capacity`)
- `minParticipants`: Minimum number of participants
- `participants`: Array of participant email addresses or user IDs
- `neighborhood`: Event neighborhood (e.g., "greenwich-village", "hells-kitchen")
- `venueName`: Name of the venue
- `venueId`: Venue ID reference
- `categories`: Array of category strings (e.g., ["CUBAN", "ITALIAN"])
- `features`: Array of feature strings or null
- `ownerId`: User ID of event creator
- `description`: Event description text
- `eventStatus`: Event status (e.g., "approved")
- `active`: Boolean indicating if event is active

**Important Field Mappings:**
- Use `type == "public"` to check if event is public (NOT `isPrivate == False`)
- Use `maxParticipants` for capacity (NOT `capacity`)
- Use `name` for event title (NOT `title`)
- Use `startDate` for event date (NOT `date`)

### Firebase Structure

```
leo/
├── campaigns/
│   └── {campaign_id}/
│       ├── metadata/
│       ├── users/
│       ├── events/
│       ├── matches/
│       └── messages/
├── prompts/
│   └── {prompt_id}/
└── reports/
    └── {report_id}/
```

## Campaign Flow

1. **User Selection**: Fetch users with most event attendance and complete profiles (max 10)
2. **Event Selection**: Identify public events with <50% participation
3. **Summary Generation**: Create summaries for users and events
4. **AI Matching**: Use Claude to match users to events with scoring and reasoning
5. **Message Generation**: Create personalized invitation messages
6. **Data Persistence**: Save all data to Firebase
7. **Reporting**: Generate and save final campaign report

## Output

- **Log File**: `fill_the_table_YYYYMMDD_HHMMSS.log`
- **Firebase**: All campaign data saved under `leo/campaigns/{campaign_id}`
- **Report**: Saved under `leo/reports/report-{campaign_id}`

## Matching Criteria

The AI considers:
- Interest alignment with event category
- Location proximity
- Engagement history
- Diversity of perspectives

Each match includes:
- Match score (1-10)
- Reasoning for the match
- Personalized invitation message
