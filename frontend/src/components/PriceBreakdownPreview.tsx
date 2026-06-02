/**
 * PriceBreakdownPreview
 * Renders the base / GST / payable split for a booking, using the backend
 * tax-preview endpoint as the single source of truth.
 *
 * Used in two places today:
 *   - Owner billing settings page (so the owner sees exactly what the student will see)
 *   - Student booking checkout (display-only; the actual amount charged is
 *     still driven by the existing booking flow)
 *
 * IMPORTANT: this component never changes pricing. It only renders what the
 * backend would compute. With `feature.per_listing_price_mode` OFF, the
 * preview reflects the existing GST-inclusive behavior. The component shows a
 * tag when the listing's price_display_mode is different from the mode
 * actually being applied, so neither the owner nor the student is misled.
 */
import React, { useEffect, useState } from 'react';
import { AlertCircle, Info } from 'lucide-react';
import { taxPreviewService, TaxPreviewResponse } from '../services/taxPreviewService';

interface Props {
  listingType: 'reading-room' | 'accommodation';
  listingId: string;
  displayedPrice: number;
  placeOfSupplyState?: string | null;
  /** Show explanatory notes (default: yes). Hide in tight student-side embeds. */
  showNotes?: boolean;
  /** Compact rendering for inline use in checkout summaries. */
  compact?: boolean;
}

const formatINR = (n: number) =>
  n.toLocaleString('en-IN', { style: 'currency', currency: 'INR' });

export const PriceBreakdownPreview: React.FC<Props> = ({
  listingType,
  listingId,
  displayedPrice,
  placeOfSupplyState,
  showNotes = true,
  compact = false,
}) => {
  const [data, setData] = useState<TaxPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      if (displayedPrice <= 0) {
        setData(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const res = await taxPreviewService.preview({
          listing_type: listingType,
          listing_id: listingId,
          displayed_price: displayedPrice,
          place_of_supply_state: placeOfSupplyState ?? null,
        });
        if (!cancelled) setData(res);
      } catch (e: any) {
        if (!cancelled) {
          // 404 (preview endpoint unmounted in older deployments) -> fail soft.
          if (e?.response?.status === 404) {
            setError(null);
            setData(null);
          } else {
            setError(e?.response?.data?.detail || 'Could not compute preview.');
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [listingType, listingId, displayedPrice, placeOfSupplyState]);

  if (displayedPrice <= 0) return null;
  if (loading && !data) {
    return <div className="text-xs text-gray-400">Computing tax…</div>;
  }
  if (error) {
    return (
      <div className="text-xs text-amber-700 flex items-center gap-1">
        <AlertCircle className="w-3 h-3" /> {error}
      </div>
    );
  }
  if (!data) return null;

  if (compact) {
    return (
      <div className="text-xs text-gray-500">
        {data.treatment === 'NOT_REGISTERED' ? (
          <span>No GST charged ({data.treatment})</span>
        ) : (
          <span>
            Incl. GST {formatINR(data.gst_amount)}
            {data.gst_rate_applied > 0 && ` @ ${(data.gst_rate_applied * 100).toFixed(0)}%`}
          </span>
        )}
      </div>
    );
  }

  const showMismatch =
    data.listing_mode &&
    !data.per_listing_flag_on &&
    data.listing_mode !== data.effective_mode;

  return (
    <div className="border rounded-lg p-4 bg-gray-50">
      <div className="text-xs font-medium text-gray-500 uppercase mb-3">Price breakdown</div>
      <div className="grid grid-cols-2 gap-y-1 text-sm">
        <div className="text-gray-600">Taxable value</div>
        <div className="text-right text-gray-900">{formatINR(data.base_amount)}</div>

        {data.cgst > 0 && (
          <>
            <div className="text-gray-600">
              CGST {data.gst_rate_applied > 0 && `@ ${((data.gst_rate_applied * 100) / 2).toFixed(1)}%`}
            </div>
            <div className="text-right text-gray-900">{formatINR(data.cgst)}</div>
            <div className="text-gray-600">
              SGST {data.gst_rate_applied > 0 && `@ ${((data.gst_rate_applied * 100) / 2).toFixed(1)}%`}
            </div>
            <div className="text-right text-gray-900">{formatINR(data.sgst)}</div>
          </>
        )}
        {data.igst > 0 && (
          <>
            <div className="text-gray-600">
              IGST {data.gst_rate_applied > 0 && `@ ${(data.gst_rate_applied * 100).toFixed(0)}%`}
            </div>
            <div className="text-right text-gray-900">{formatINR(data.igst)}</div>
          </>
        )}

        <div className="col-span-2 border-t border-gray-200 mt-1" />
        <div className="font-semibold text-gray-900">Total payable</div>
        <div className="text-right font-semibold text-gray-900">{formatINR(data.payable_amount)}</div>
      </div>

      {showNotes && (
        <div className="mt-3 space-y-1">
          <div className="text-xs text-gray-500 flex items-start gap-1">
            <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
            <span>
              Effective mode: <code className="bg-white px-1 rounded">{data.effective_mode}</code>
              {data.listing_mode && ` (listing set to ${data.listing_mode})`}
            </span>
          </div>
          {showMismatch && (
            <div className="text-xs text-amber-700 flex items-start gap-1">
              <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
              <span>
                Listing prefers <b>{data.listing_mode}</b> but the platform's
                per-listing flag is off — the global default is in effect.
                Super-admin can enable <code>feature.per_listing_price_mode</code>{' '}
                in Tax Config to honour this listing's preference.
              </span>
            </div>
          )}
          {data.notes.map((n, i) => (
            <div key={i} className="text-xs text-gray-500 flex items-start gap-1">
              <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
              <span>{n}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default PriceBreakdownPreview;
