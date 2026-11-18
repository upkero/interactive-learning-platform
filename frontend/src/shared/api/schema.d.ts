export interface paths {
  "/auth/login": {
    post: {
      requestBody: {
        content: {
          "application/json": {
            email: string;
            password: string;
          };
        };
      };
      responses: {
        200: {
          content: {
            "application/json": components["schemas"]["User"];
          };
        };
      };
    };
  };
  "/auth/register": {
    post: {
      requestBody: {
        content: {
          "application/json": {
            email: string;
            password: string;
          };
        };
      };
      responses: {
        201: {
          content: {
            "application/json": components["schemas"]["User"];
          };
        };
      };
    };
  };
  "/auth/logout": {
    post: {
      responses: {
        204: {
          content?: never;
        };
      };
    };
  };
  "/me": {
    get: {
      responses: {
        200: {
          content: {
            "application/json": components["schemas"]["User"];
          };
        };
      };
    };
    patch: {
      requestBody: {
        content: {
          "application/json": {
            notify_by_email?: boolean;
            locale?: "ru" | "en";
          };
        };
      };
      responses: {
        200: {
          content: {
            "application/json": components["schemas"]["User"];
          };
        };
      };
    };
  };
  "/me/quota": {
    get: {
      responses: {
        200: {
          content: {
            "application/json": components["schemas"]["Quota"];
          };
        };
      };
    };
  };
  "/documents": {
    get: {
      parameters: {
        query?: {
          scope?: "all" | "mine" | "shared";
        };
      };
      responses: {
        200: {
          content: {
            "application/json": components["schemas"]["DocumentSummary"][];
          };
        };
      };
    };
    post: {
      requestBody: {
        content: {
          "multipart/form-data": {
            file?: File;
            google_doc_url?: string;
          };
        };
      };
      responses: {
        201: {
          content: {
            "application/json": components["schemas"]["DocumentDetail"];
          };
        };
      };
    };
  };
  "/documents/{id}": {
    get: {
      parameters: {
        path: {
          id: string;
        };
      };
      responses: {
        200: {
          content: {
            "application/json": components["schemas"]["DocumentDetail"];
          };
        };
      };
    };
    delete: {
      parameters: {
        path: {
          id: string;
        };
      };
      responses: {
        204: {
          content?: never;
        };
      };
    };
  };
  "/documents/{id}/generate": {
    post: {
      parameters: {
        path: {
          id: string;
        };
      };
      requestBody: {
        content: {
          "application/json": components["schemas"]["GenerateRequest"];
        };
      };
      responses: {
        202: {
          content: {
            "application/json": {
              status: "generating";
            };
          };
        };
      };
    };
  };
}

export interface components {
  schemas: {
    ErrorCode:
      | "not_authenticated"
      | "invalid_credentials"
      | "email_already_registered"
      | "forbidden"
      | "not_found"
      | "validation_error"
      | "file_too_large"
      | "unsupported_file_type"
      | "empty_document"
      | "google_doc_unreachable"
      | "parsing_failed"
      | "no_topics_selected"
      | "invalid_document_state"
      | "quota_exceeded"
      | "generation_conflict"
      | "part_generation_failed"
      | "widget_generation_failed"
      | "share_self_forbidden"
      | "share_user_not_found"
      | "rate_limit_exceeded"
      | "internal_error"
      | "network_error"
      | "unknown_error";
    ApiErrorPayload: {
      error_code: components["schemas"]["ErrorCode"];
      message: string;
      details?: Record<string, unknown>;
    };
    User: {
      id: string;
      email: string;
      locale: "ru" | "en";
      notify_by_email: boolean;
      last_answers?: {
        level: "novice" | "intermediate" | "advanced";
        depth: "overview" | "standard" | "deep";
        goal: "refresh" | "exam" | "practice";
      };
    };
    Quota: {
      remaining: number;
      total: number;
      resets_at?: string;
    };
    DocumentStatus:
      | "parsing"
      | "topics_required"
      | "questions_required"
      | "generating"
      | "ready"
      | "error";
    DocumentSummary: {
      id: string;
      title: string;
      status: components["schemas"]["DocumentStatus"];
      created_at: string;
      is_shared: boolean;
      error_code?: components["schemas"]["ErrorCode"];
    };
    TopicNode: {
      id: string;
      title: string;
      cost: number;
      children?: components["schemas"]["TopicNode"][];
    };
    DocumentDetail: {
      id: string;
      title: string;
      status: components["schemas"]["DocumentStatus"];
      topics?: components["schemas"]["TopicNode"][];
      error_code?: components["schemas"]["ErrorCode"];
    };
    GenerateRequest: {
      topic_ids: string[];
      level: "novice" | "intermediate" | "advanced";
      depth: "overview" | "standard" | "deep";
      goal: "refresh" | "exam" | "practice";
    };
  };
}
