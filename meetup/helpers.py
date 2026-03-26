"""
Meetup integration helpers.

GraphQL queries, mutations, and shared utilities for the Meetup API.
"""

MEETUP_GQL_URL = "https://api.meetup.com/gql"


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

GET_SELF_QUERY = """
query {
  self {
    id
    name
    email
    memberSince
    photo {
      baseUrl
    }
  }
}
"""

LIST_GROUPS_QUERY = """
query($first: Int) {
  self {
    organizedGroups(input: { first: $first }) {
      edges {
        node {
          id
          name
          urlname
          membersCount
          city
          country
          description
          link
        }
      }
    }
  }
}
"""

GET_GROUP_QUERY = """
query($urlname: String!) {
  groupByUrlname(urlname: $urlname) {
    id
    name
    urlname
    membersCount
    city
    country
    description
    link
    timezone
  }
}
"""

LIST_EVENTS_QUERY = """
query($urlname: String!, $first: Int, $past: Boolean) {
  groupByUrlname(urlname: $urlname) {
    events(input: { first: $first, past: $past }) {
      edges {
        node {
          id
          title
          description
          dateTime
          duration
          status
          eventUrl
          venue {
            id
            name
            address
            city
          }
        }
      }
    }
  }
}
"""

GET_EVENT_QUERY = """
query($eventId: ID!) {
  event(id: $eventId) {
    id
    title
    description
    dateTime
    duration
    status
    eventUrl
    going
    isOnline
    venue {
      id
      name
      address
      city
    }
    group {
      id
      name
      urlname
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

CREATE_EVENT_MUTATION = """
mutation($input: CreateEventInput!) {
  createEvent(input: $input) {
    event {
      id
      title
      dateTime
      status
      eventUrl
    }
    errors {
      message
      code
      field
    }
  }
}
"""

UPDATE_EVENT_MUTATION = """
mutation($input: EditEventInput!) {
  editEvent(input: $input) {
    event {
      id
      title
      dateTime
      status
      eventUrl
    }
    errors {
      message
      code
      field
    }
  }
}
"""

DELETE_EVENT_MUTATION = """
mutation($input: DeleteEventInput!) {
  deleteEvent(input: $input) {
    success
    errors {
      message
      code
    }
  }
}
"""

PUBLISH_EVENT_MUTATION = """
mutation($input: PublishEventInput!) {
  publishEvent(input: $input) {
    event {
      id
      title
      status
      eventUrl
    }
    errors {
      message
      code
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def extract_gql_errors(response: dict) -> str | None:
    """
    Return a formatted error string if the GraphQL response contains errors,
    otherwise return None.

    Checks both top-level `errors` (transport/auth errors) and
    mutation-level `errors` arrays inside `data`.
    """
    if response.get("errors"):
        msgs = [e.get("message", str(e)) for e in response["errors"]]
        return "; ".join(msgs)

    data = response.get("data", {})
    for key in data:
        mutation_result = data[key]
        if isinstance(mutation_result, dict):
            nested = mutation_result.get("errors")
            if nested:
                msgs = [e.get("message", str(e)) for e in nested]
                return "; ".join(msgs)

    return None
