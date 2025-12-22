# User Selection Pipeline - Step 1

## Overview

This document describes the user selection pipeline that filters users based on qualification criteria for messaging campaigns. The pipeline identifies which users have received messages and which users should be filtered out due to missing required fields for personalization.

## User Schema (from MongoDB)

The `users.json` file contains user data from MongoDB with the following schema:

### Core Identity Fields
- `_id` (string): MongoDB ObjectId as string
- `id` (string): User identifier (typically same as `_id`)
- `firstName` (string): User's first name
- `lastName` (string): User's last name
- `email` (string): User's email address
- `phone` (string): User's phone number (format: "+1...")
- `username` (string): Username/login identifier

### Profile Fields
- `gender` (string): User's gender (e.g., "male", "female", "other")
- `birthDay` (string, nullable): Date of birth in ISO 8601 format
- `homeNeighborhood` (string): User's home neighborhood (e.g., "midtown-east", "hells-kitchen")
- `workNeighborhood` (string, nullable): User's work neighborhood
- `interests` (array): Array of interest strings (e.g., ["art", "music", "eatingOut", "travel"])
- `occupation` (string): User's occupation (e.g., "Finance", "Tech Founder", "Professional")
- `relationshipStatus` (string): Relationship status (e.g., "single", "married", "other")
- `tableTypePreference` (string): Table preference (e.g., "social", "both", "intimate")

### Status & Metadata Fields
- `role` (string): User role (e.g., "REGULAR", "ADMIN", "AMBASSADOR", "POTENTIAL")
- `status` (number): Status code (2 = active)
- `active` (boolean): Whether account is active
- `createdAt` (string): Account creation date in ISO 8601 format
- `phoneNumberVerified` (boolean): Whether phone number is verified

### Additional Fields
- `imageUrl` (string, nullable): Profile image URL
- `credit` (number): Account credit balance
- `allergies` (string, nullable): Dietary allergies
- `defaultPayment` (string, nullable): Default payment method
- `defaultTip` (number): Default tip percentage
- Various other metadata fields

## Messages Schema

The `messages.json` file contains message data with the following schema:

### Core Message Fields
- `message` (string): The generated SMS message text
- `user_id` (string): User identifier linking to user's `id` or `_id` field
- `user_name` (string): User's full name
- `user_email` (string): User's email address
- `user_phone` (string): User's phone number

### Event Context Fields
- `event_id` (string): Event identifier
- `event_name` (string): Name of the event
- `event_date` (string): Event date in ISO 8601 format
- `event_summary` (string): Summary description of the event

### Personalization Fields
- `user_summary` (string): Comprehensive user profile summary
- `personalization_notes` (string): Notes used for message personalization
- `reasoning` (string): Reasoning for message approach
- `confidence_percentage` (number): Confidence score (0-100)

### Campaign Fields
- `campaign` (string): Campaign type (e.g., "Fill The Table", "Seat the Newcomer", "Return To Table")
- `airtable_id` (string, nullable): Airtable record ID

## Qualification Criteria

Users must have the following fields filled out to be qualified for messaging campaigns. These fields are essential for personalizing messages effectively:

### Required Fields for Personalization

1. **`interests`** (array)
   - **Purpose**: Required for event matching and personalization
   - **Requirement**: Must be a non-empty array/list
   - **Usage**: Used to match users with events that align with their interests

2. **`phone`** (string)
   - **Purpose**: Required for SMS delivery
   - **Requirement**: Must be a non-empty string
   - **Usage**: Primary channel for message delivery

3. **`email`** (string)
   - **Purpose**: Required for backup contact and verification
   - **Requirement**: Must be a non-empty string
   - **Usage**: Secondary contact method and user identification

4. **`homeNeighborhood`** (string)
   - **Purpose**: Required for location-based personalization
   - **Requirement**: Must be a non-empty string
   - **Usage**: Used to match users with nearby events and personalize location references

5. **`occupation`** (string)
   - **Purpose**: Required for occupation-based personalization
   - **Requirement**: Must be a non-empty string
   - **Usage**: Used to tailor messages to professional context

6. **`gender`** (string)
   - **Purpose**: Required for gender-based personalization
   - **Requirement**: Must be a non-empty string
   - **Usage**: Used for appropriate event matching and messaging tone

7. **`relationshipStatus`** (string)
   - **Purpose**: Required for relationship context in messaging
   - **Requirement**: Must be a non-empty string
   - **Usage**: Used to understand user's social context for event recommendations

8. **`tableTypePreference`** (string)
   - **Purpose**: Required for table preference matching
   - **Requirement**: Must be a non-empty string
   - **Usage**: Used to match users with events that match their preferred table type

9. **`workNeighborhood`** (string)
   - **Purpose**: Required for work location-based personalization
   - **Requirement**: Must be a non-empty string
   - **Usage**: Used to match users with events near their workplace

### Filtering Logic

The pipeline applies two levels of filtering:

1. **Users who received messages**: Users whose `id` or `_id` appears in the `user_id` field of any message in `messages.json` are filtered out to avoid duplicate messaging.

2. **Users missing required fields**: Users missing any of the 9 required fields listed above are filtered out, as they cannot be effectively personalized.

## Results

*Results from pipeline execution on 2025-12-21 20:18:20*

### Filtering Statistics

- **Total users loaded**: 10,069
- **Users who received messages (filtered out)**: 40
- **Users remaining after message filter**: 10,029
- **Users missing required fields (filtered out)**: 9,990
  - Missing `interests`: 7,707
  - Missing `phone`: 737
  - Missing `email`: 274
  - Missing `homeNeighborhood`: 9,220
  - Missing `occupation`: 9,437
  - Missing `gender`: 6,948
  - Missing `relationshipStatus`: 8,331
  - Missing `tableTypePreference`: 8,325
  - Missing `workNeighborhood`: 9,686
- **Final qualified users**: 39

### Analysis

The pipeline results reveal significant data quality challenges in the user database:

1. **Profile Completeness is Low**: Only 39 out of 10,069 users (0.39%) have all required fields filled out. This indicates that most users have incomplete profiles.

2. **Most Critical Missing Fields**:
   - **workNeighborhood**: 9,686 users missing (96.2% of users after message filter)
   - **occupation**: 9,437 users missing (94.1%)
   - **homeNeighborhood**: 9,220 users missing (91.9%)
   - **relationshipStatus**: 8,331 users missing (83.0%)
   - **tableTypePreference**: 8,325 users missing (83.0%)

3. **Moderate Missing Fields**:
   - **interests**: 7,707 users missing (76.8%) - Critical for personalization
   - **gender**: 6,948 users missing (69.3%)

4. **Contact Information**:
   - **phone**: 737 users missing (7.3%) - Relatively good coverage
   - **email**: 274 users missing (2.7%) - Excellent coverage

5. **Key Insights**:
   - The vast majority of users are missing location-based fields (`workNeighborhood`, `homeNeighborhood`)
   - Many users lack basic profile information (`occupation`, `relationshipStatus`, `tableTypePreference`)
   - Contact information (phone, email) is well-populated, suggesting users can be reached
   - The low qualification rate (0.39%) suggests a need for profile completion campaigns or relaxed requirements for certain fields

6. **Recommendations**:
   - Consider making `workNeighborhood` optional if `homeNeighborhood` is present
   - Prioritize collecting `interests` data as it's critical for personalization
   - The 39 qualified users represent a highly engaged segment with complete profiles

