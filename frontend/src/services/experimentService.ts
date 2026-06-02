/**
 * Phase 6 — experiments + cohorts + ML feature export.
 */
import api from './api';

export type ExperimentStatus = 'DRAFT' | 'RUNNING' | 'PAUSED' | 'COMPLETED';

export interface Variant { name: string; weight: number; }

export interface Experiment {
    id: string;
    slug: string;
    name: string;
    description: string | null;
    hypothesis: string | null;
    variants: Variant[];
    success_event_name: string;
    status: ExperimentStatus;
    starts_at: string | null;
    ends_at: string | null;
    created_at: string;
    updated_at: string;
}

export interface ExperimentInput {
    slug: string;
    name: string;
    description?: string | null;
    hypothesis?: string | null;
    variants: Variant[];
    success_event_name?: string;
    starts_at?: string | null;
    ends_at?: string | null;
}

export interface ExperimentPatch {
    name?: string;
    description?: string | null;
    hypothesis?: string | null;
    status?: ExperimentStatus;
    success_event_name?: string;
    starts_at?: string | null;
    ends_at?: string | null;
}

export interface VariantResult {
    variant: string;
    exposures: number;
    converters: number;
    conversions_total: number;
    conversion_rate: number;
}

export interface ExperimentResults {
    slug: string;
    status: string;
    control_variant: string | null;
    variants: VariantResult[];
    significance: Record<string, {
        z: number | null;
        is_significant_at_95: boolean;
        lift: number;
    }>;
}

export interface CohortRow {
    cohort_week: string;
    size: number;
    retention: number[];
    retention_counts: number[];
}

export interface CohortReport {
    enabled: boolean;
    cohort_kind?: string;
    weeks?: number;
    rows?: CohortRow[];
}

export const experimentService = {
    async list(): Promise<Experiment[]> {
        const res = await api.get<Experiment[]>('/api/super-admin/experiments');
        return res.data;
    },
    async create(input: ExperimentInput): Promise<Experiment> {
        const res = await api.post<Experiment>('/api/super-admin/experiments', input);
        return res.data;
    },
    async patch(id: string, body: ExperimentPatch): Promise<Experiment> {
        const res = await api.patch<Experiment>(`/api/super-admin/experiments/${id}`, body);
        return res.data;
    },
    async results(slug: string): Promise<ExperimentResults> {
        const res = await api.get<ExperimentResults>(
            `/api/super-admin/experiments/${slug}/results`,
        );
        return res.data;
    },
    async cohorts(
        cohortKind: 'search_first' | 'booking_first' = 'search_first',
        n_cohort_weeks = 8,
        n_retention_weeks = 8,
    ): Promise<CohortReport> {
        const res = await api.get<CohortReport>('/api/super-admin/cohorts/weekly', {
            params: {
                cohort_kind: cohortKind,
                n_cohort_weeks, n_retention_weeks,
            },
        });
        return res.data;
    },
    featureCsvUrl(windowDays = 30): string {
        return `/api/super-admin/ml/features.csv?window_days=${windowDays}`;
    },
};
