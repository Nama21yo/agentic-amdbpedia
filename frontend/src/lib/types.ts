export interface MappingCandidate {
	property: string;
	class: string;
	score: number;
	payload?: Record<string, unknown>;
}

export interface AgentStep {
	node: string;
	status: 'running' | 'done' | 'error';
	detail?: string;
	timestamp?: string;
}

export interface PredictedMapping {
	templateProperty: string;
	ontologyProperty: string;
	confidence: number;
}

/**
 * The pipeline's `format_mapping_syntax` step always computes both of
 * these deterministically alongside `mappings` (`mcp_server/pipeline.py`)
 * — the same MediaWiki `{{TemplateMapping ...}}` wikitext a publish would
 * actually write, and its XML-syntax equivalent. Not persisted on
 * `ReviewItem`: cheaply regenerable from `mappings`/`domainClass` at any
 * time, so nothing worth duplicating in Postgres.
 */
export interface MappingSyntax {
	mappingWikitext: string;
	xmlRules: string;
}

export interface ChatMessage {
	role: 'user' | 'assistant';
	content: string;
}

export type ReviewStatus = 'pending_review' | 'approved' | 'rejected' | 'published';

export interface ReviewItem {
	id: string;
	templateName: string;
	domainClass: string;
	status: ReviewStatus;
	submittedAt: string;
	mappings: PredictedMapping[];
}

export interface CoverageStats {
	totalTemplates: number;
	mappedTemplates: number;
	coveragePercent: number;
	lastRunAt?: string;
}
