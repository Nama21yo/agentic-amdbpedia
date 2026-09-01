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
