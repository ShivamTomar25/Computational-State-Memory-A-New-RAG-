from __future__ import annotations

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.memory_systems.graph_rag.enums import GraphRAGProviderName
from app.memory_systems.hippo_rag.enums import HippoRAGProviderName


class Settings(BaseSettings):
    app_name: str = "Project 1 API"
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    supabase_url: Optional[str] = None
    supabase_secret_key: Optional[str] = None
    supabase_storage_bucket: str = "clinical-documents"
    supabase_signed_upload_expiry_seconds: int = 600
    supabase_signed_download_expiry_seconds: int = 300
    document_max_file_size_bytes: int = 20 * 1024 * 1024
    document_allowed_content_types: str = (
        "application/pdf,"
        "text/plain,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    document_storage_environment: str = "development"
    document_upload_completion_deadline_seconds: int = 1800
    document_processing_pipeline_version: int = 1
    document_max_pdf_pages: int = 500
    document_max_extracted_characters: int = 5_000_000
    document_max_docx_uncompressed_bytes: int = 100 * 1024 * 1024
    document_max_docx_entries: int = 5000
    document_text_min_total_characters: int = 50
    document_text_min_average_characters_per_page: int = 20
    document_text_max_empty_page_ratio: float = 0.8
    document_processing_max_attempts: int = 3
    document_processing_retry_base_seconds: int = 30
    document_temp_directory: Optional[str] = None
    document_store_raw_extracted_text: bool = True
    document_store_normalized_text: bool = True
    memory_systems_enabled: bool = True
    memory_default_top_k: int = 8
    memory_max_top_k: int = 50
    memory_default_context_token_budget: int = 6000
    memory_max_context_token_budget: int = 20000
    memory_pipeline_version: int = 1
    memory_embedding_provider: str = "deterministic"
    memory_embedding_model: str = "sustha-deterministic-hash-embedding"
    memory_embedding_device: str = "cpu"
    memory_embedding_normalize: bool = True
    memory_embedding_batch_size: int = 32
    memory_embedding_dimension: int = 64
    langgraph_checkpointer_provider: str = "memory"
    langgraph_checkpointer_schema: str = "langgraph_checkpoint"
    dense_rag_chunk_size_tokens: int = 700
    dense_rag_chunk_overlap_tokens: int = 100
    dense_rag_top_k: int = 8
    hybrid_dense_candidates: int = 20
    hybrid_lexical_candidates: int = 20
    hybrid_final_top_k: int = 8
    hybrid_rrf_k: int = 60
    hybrid_text_search_language: str = "english"
    long_context_max_tokens: int = 16000
    rolling_summary_recent_window_tokens: int = 3000
    graphrag_provider: GraphRAGProviderName = GraphRAGProviderName.UNAVAILABLE
    graphrag_storage_directory: str = ".local/graphrag"
    hipporag_provider: HippoRAGProviderName = HippoRAGProviderName.UNAVAILABLE
    hipporag_storage_directory: str = ".local/hipporag"
    csm_activation_top_k: int = 20
    csm_activation_token_budget: int = 6000
    csm_v3_top_k_states: int = 4
    csm_v3_top_k_evidence: int = 4
    csm_v3_context_token_budget: int = 1800
    csm_v3_activation_threshold: float = 0.18
    csm_v3_max_dependency_depth: int = 2
    csm_v3_max_dependency_fanout: int = 6
    csm_v4_top_k_states: int = 6
    csm_v4_top_k_evidence: int = 8
    csm_v4_context_token_budget: int = 2600
    csm_v4_simple_state_token_budget: int = 1600
    csm_v4_ordinary_token_budget: int = 2000
    csm_v4_temporal_token_budget: int = 2400
    csm_v4_summary_token_budget: int = 2600
    csm_v4_activation_threshold: float = 0.14
    csm_v4_candidate_recall_limit: int = 24
    csm_v4_support_evidence_per_state: int = 2
    csm_v4_correction_evidence_per_state: int = 3
    csm_v4_max_dependency_depth: int = 2
    csm_v4_max_dependency_fanout: int = 8
    groq_api_key: Optional[str] = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_fallback_model: Optional[str] = "llama-3.3-70b-versatile"
    groq_allow_fallback: bool = False
    groq_temperature: float = 0
    groq_max_retries: int = 2
    groq_timeout_seconds: int = 120
    groq_max_concurrency: int = 2
    groq_answer_max_tokens: int = 2048
    groq_extraction_max_tokens: int = 4096
    groq_summary_max_tokens: int = 4096
    groq_graph_max_tokens: int = 4096
    llm_provider: str = "groq"
    llm_experiment_mode: bool = False
    llm_prompt_version: int = 1
    llm_external_data_mode: str = "synthetic_or_deidentified"
    llm_allow_identifiable_clinical_data: bool = False
    evaluation_profile: str = "smoke"
    evaluation_repeats: int = 3
    evaluation_random_seed: int = 42
    evaluation_max_concurrency: int = 1
    evaluation_require_all_systems_ready: bool = True
    evaluation_fail_on_model_mismatch: bool = True
    evaluation_fail_on_prompt_mismatch: bool = True
    evaluation_fail_on_source_cutoff_mismatch: bool = True
    evaluation_fail_on_token_budget_mismatch: bool = True
    evaluation_judge_provider: str = "groq"
    evaluation_judge_model: Optional[str] = None
    evaluation_judge_repeats: int = 3
    evaluation_judge_min_confidence: float = 0.70
    evaluation_require_distinct_judge_model: bool = False
    evaluation_calibration_bins: int = 10
    evaluation_aggregate_enabled: bool = False
    performance_monitoring_enabled: bool = True
    performance_server_timing_enabled: bool = True
    performance_api_enabled: bool = True
    performance_slow_request_ms: int = 500
    performance_slow_query_ms: int = 100
    performance_slow_job_ms: int = 5000
    cache_provider: str = "memory"
    cache_default_ttl_seconds: int = 60
    cache_max_entries: int = 5000
    cache_redis_url: Optional[str] = None
    cache_key_prefix: str = "sustha"
    api_compression_enabled: bool = True
    api_compression_minimum_size_bytes: int = 1024
    database_pool_size: int = 10
    database_max_overflow: int = 10
    database_pool_timeout_seconds: int = 30
    database_pool_recycle_seconds: int = 1800

    @field_validator(
        "supabase_signed_upload_expiry_seconds",
        "supabase_signed_download_expiry_seconds",
        "document_max_file_size_bytes",
        "document_upload_completion_deadline_seconds",
        "document_processing_pipeline_version",
        "document_max_pdf_pages",
        "document_max_extracted_characters",
        "document_max_docx_uncompressed_bytes",
        "document_max_docx_entries",
        "document_text_min_total_characters",
        "document_text_min_average_characters_per_page",
        "document_processing_max_attempts",
        "document_processing_retry_base_seconds",
        "memory_default_top_k",
        "memory_max_top_k",
        "memory_default_context_token_budget",
        "memory_max_context_token_budget",
        "memory_pipeline_version",
        "memory_embedding_batch_size",
        "memory_embedding_dimension",
        "dense_rag_chunk_size_tokens",
        "dense_rag_chunk_overlap_tokens",
        "dense_rag_top_k",
        "hybrid_dense_candidates",
        "hybrid_lexical_candidates",
        "hybrid_final_top_k",
        "hybrid_rrf_k",
        "long_context_max_tokens",
        "rolling_summary_recent_window_tokens",
        "csm_activation_top_k",
        "csm_activation_token_budget",
        "csm_v3_top_k_states",
        "csm_v3_top_k_evidence",
        "csm_v3_context_token_budget",
        "csm_v3_max_dependency_depth",
        "csm_v3_max_dependency_fanout",
        "csm_v4_top_k_states",
        "csm_v4_top_k_evidence",
        "csm_v4_context_token_budget",
        "csm_v4_simple_state_token_budget",
        "csm_v4_ordinary_token_budget",
        "csm_v4_temporal_token_budget",
        "csm_v4_summary_token_budget",
        "csm_v4_candidate_recall_limit",
        "csm_v4_support_evidence_per_state",
        "csm_v4_correction_evidence_per_state",
        "csm_v4_max_dependency_depth",
        "csm_v4_max_dependency_fanout",
        "groq_max_retries",
        "groq_timeout_seconds",
        "groq_max_concurrency",
        "groq_answer_max_tokens",
        "groq_extraction_max_tokens",
        "groq_summary_max_tokens",
        "groq_graph_max_tokens",
        "llm_prompt_version",
        "evaluation_repeats",
        "evaluation_random_seed",
        "evaluation_max_concurrency",
        "evaluation_judge_repeats",
        "evaluation_calibration_bins",
        "performance_slow_request_ms",
        "performance_slow_query_ms",
        "performance_slow_job_ms",
        "cache_default_ttl_seconds",
        "cache_max_entries",
        "api_compression_minimum_size_bytes",
        "database_pool_size",
        "database_max_overflow",
        "database_pool_timeout_seconds",
        "database_pool_recycle_seconds",
    )
    @classmethod
    def validate_positive_integer(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Value must be greater than zero.")

        return value

    @field_validator("groq_api_key", "groq_fallback_model", mode="before")
    @classmethod
    def empty_string_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None

        return value

    @field_validator("groq_temperature")
    @classmethod
    def validate_temperature(cls, value: float) -> float:
        if value < 0 or value > 2:
            raise ValueError("Temperature must be between zero and two.")

        return value

    @field_validator("llm_external_data_mode")
    @classmethod
    def validate_data_egress_mode(cls, value: str) -> str:
        allowed = {
            "disabled",
            "synthetic_only",
            "synthetic_or_deidentified",
            "explicitly_authorized",
        }

        if value not in allowed:
            raise ValueError("Invalid LLM external data mode.")

        return value

    @field_validator("document_text_max_empty_page_ratio")
    @classmethod
    def validate_ratio(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("Value must be between zero and one.")

        return value

    @field_validator(
        "supabase_storage_bucket",
        "document_storage_environment",
        "graphrag_storage_directory",
        "hipporag_storage_directory",
    )
    @classmethod
    def validate_non_empty_string(cls, value: str) -> str:
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("Value cannot be empty.")

        return cleaned_value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
