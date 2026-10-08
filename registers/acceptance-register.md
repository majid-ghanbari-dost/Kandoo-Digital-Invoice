# Acceptance Register — Kandoo Digital Invoice

```text
Register ID:  REG-AR | Version: 1.0 | Date: 2026-10-01 | Owner: QA + Technical Manager | Approver: Product Owner (G3/G4)
Chain:        WP → Task → Deliverable → Test Evidence → Acceptance Status
Rule:         هیچ AC بدون Evidence ثبت‌شده بسته نمی‌شود. وضعیت فقط: PENDING / PASS / FAIL / BLOCKED
```

## WP-1.1 — Capture Foundation: Durable Capture Store & Integrity

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-1.1.1 | WP-1.1 | با ثبت یک artifact جدید، یک Capture Record با capture_id یکتا به‌صورت دائمی local ذخیره و پس از restart قابل بازیابی است | اجرای تست ایجاد/بازیابی با گام restart | گزارش تست + dump رکورد بازیابی‌شده | T-1.1.2 | Capture Store Component | kandoo/src/capture/tests/test_store.py::test_complete_grants_and_record_is_completed + test_content_read_is_byte_exact؛ restart: kandoo/src/capture/tests/test_e2e.py::test_full_mvp_journey + kandoo/src/run_smoke.py (گام‌های ۱ و ۴) | PASS | TM (T-1.1.6) / 2026-10-01 |
| AC-1.1.2 | WP-1.1 | محاسبه S1 قطعی و حساس به محتوا است: ≥2 ورودی با محتوای یکسان → S1 برابر؛ جهش تک‌بایتی محتوا → S1 متفاوت | property test + mutation test | گزارش تست با ورودی/خروجی S1 | T-1.1.3 | S1 Fingerprint Service | kandoo/src/capture/tests/test_s1.py::test_determinism_same_bytes_same_s1 + test_known_vector_abc + test_single_byte_mutation_changes_s1 + test_empty_and_large_inputs_deterministic + test_aggregation_determinism_v1_1_c3 (الگوریتم اعلامی: SHA-256 کامل، sha256-v1) | PASS | TM (T-1.1.6) / 2026-10-01 |
| AC-1.1.3 | WP-1.1 | هر رکورد ذخیره‌شده دقیقاً یک مقدار S1 دارد و lookup با مقدار S1 نتیجه قطعی برمی‌گرداند | تست ذخیره/lookup روی store | نتیجه query + رکورد مرتبط | T-1.1.3 | S1 Fingerprint Service | kandoo/src/capture/tests/test_store.py::test_attach_s1_is_one_time_and_active_only + test_find_completed_is_completed_restricted_and_deterministic + kandoo/src/capture/tests/test_ingest_idempotency.py::test_happy_path_ingest_completes | PASS | TM (T-1.1.6) / 2026-10-01 |
| AC-1.1.4 | WP-1.1 | ارسال مجدد محتوای یکسان به capture با lookup S1 شناسایی می‌شود و رکورد فعال مستقل دومی ساخته نمی‌شود (D-03: S1 → Capture Idempotency) | duplicate submission test | گزارش تست نشان‌دهنده S1 hit | T-1.1.3 | S1 Fingerprint Service | kandoo/src/capture/tests/test_ingest_idempotency.py::test_duplicate_submission_returns_existing_capture_id + test_duplicate_hit_on_failed_record_is_never_dedup_success؛ INV-C3/UAC: kandoo/src/capture/tests/test_concurrency.py::test_n_concurrent_identical_ingests_produce_exactly_one_completed + kandoo/src/capture/tests/test_store.py::test_uac_conflict_loser_is_explicit_never_completed + test_unique_index_is_storage_level_backstop + kandoo/src/run_smoke.py (گام ۳) | PASS | TM (T-1.1.6) / 2026-10-01 |
| AC-1.1.5 | WP-1.1 | verify-on-read فعال است: محتوای دستکاری‌شده → integrity fail صریح؛ محتوای سالم → pass؛ هیچ خواندن ساکتِ خراب رخ نمی‌دهد | corruption injection test | گزارش تست fail/pass | T-1.1.4 | Integrity Verification Component | kandoo/src/capture/tests/test_read_path.py::test_healthy_read_delivers_content_with_fresh_verdict + test_corruption_injection_fails_explicitly_never_delivers + test_no_content_without_same_read_verdict_is_structural + test_failed_record_can_return_to_valid_by_truthful_verification + kandoo/src/run_smoke.py (گام ۵) | PASS | TM (T-1.1.6) / 2026-10-01 |
| AC-1.1.6 | WP-1.1 | پس از خاتمه/راه‌اندازی مجدد process، همه رکوردهای قبلی readable و integrity-valid هستند | restart durability test | گزارش تست قبل/بعد از restart | T-1.1.2 | Capture Store Component | kandoo/src/capture/tests/test_e2e.py::test_full_mvp_journey (restart + sweep invariants) + kandoo/src/capture/tests/test_recovery.py::test_restart_recovery_mixed_residues_all_settled + test_recovery_is_idempotent + kandoo/src/capture/tests/test_store.py::test_content_read_is_byte_exact + kandoo/src/run_smoke.py (گام‌های ۲ و ۴) | PASS | TM (T-1.1.6) / 2026-10-01 |
| AC-1.1.7 | WP-1.1 | capture قطع‌شده در شروع بعدی به completed یا failed_incomplete صریح تسویه می‌شود؛ رکورد نیمه‌ساخت هرگز valid ارائه نمی‌شود | interruption injection test | گزارش تست سناریوی قطع | T-1.1.5 | Initial Recovery Behavior | kandoo/src/capture/tests/test_recovery.py (۷ تست: test_w2_residue_settles_content_missing، test_w3_residue_settles_s1_missing، test_w4_residue_completes_when_verification_valid، test_w4_residue_with_corrupted_content_settles_verify_failed، uniqueness-precondition، idempotence، mixed-restart) + kandoo/src/capture/tests/test_store.py::test_settlement_only_from_active_and_terminal_states_never_change | PASS | TM (T-1.1.6) / 2026-10-01 |
| AC-1.1.8 | WP-1.1 | هر رکورد فیلدهای traceability را دارد: capture_id، S1، timestamp، source_label، lineage_reserved | بازرسی schema رکورد + تست | نمونه رکورد + جدول فیلدها | T-1.1.1, T-1.1.6 | Capture Record Contract + تست تجمیعی | kandoo/src/capture/tests/test_store.py::test_record_has_exactly_14_contract_fields + test_create_active_defaults_provable_data + kandoo/src/capture/tests/test_ingest_idempotency.py::test_entry_metadata_stored_verbatim؛ lineage: Contract v1.1 §5 Extensibility Reservation (اصلاحیه C1 — فیلد فیزیکی F-14 حذف؛ پیوند فقط capture_id/S1) + kandoo/src/capture/model.py | PASS | TM (T-1.1.6) / 2026-10-01 |

```text
WP-1.1 Acceptance Status: 8/8 closed — WP-1.1: IMPLEMENTED (2026-10-01) | G3: PASS (2026-10-01 — ثبت رسمی با TM dispatch؛ شواهد = همین Register)
Note (2026-10-01, T-1.1.1): Deliverable «Capture Record Contract» (بخشی از زنجیره AC-1.1.8) تکمیل شد:
kandoo/specs/WP-1.1-capture-record-contract.md (10/10 AC-T111 PASS در §18).
[تاریخچه] در زمان این یادداشت همه ACهای اجرایی PENDING بودند (پیش از implementation).

Note (2026-10-01, T-1.1.6) — ACCEPTANCE CLOSURE (WP-1.1):
- وضعیت رسمی WP-1.1: IMPLEMENTED (تأیید TM بر گزارش WP-1.1-IMPL) — هر ۸ AC با شواهد اجرایی واقعی PASS شد (جدول بالا؛ Accepted By = TM via T-1.1.6).
- بازاجرای زنده همین روز: pytest kandoo/src/capture/tests → 54/54 PASSED (0.40s؛ Python 3.12.14 / pytest 9.0.2) + kandoo/src/run_smoke.py → SMOKE OK (ingest → read VALID → duplicate dedup → restart/recovery → tamper → FAILED).
- یادداشت AC-1.1.8: طبق Contract v1.1 (اصلاحیه تأییدشده C1) فیلد فیزیکی lineage_reserved حذف و رزرو lineage در سطح Contract (§5 Extensibility Reservation) محقق است؛ رکورد Frozen = ۱۴ فیلد. متن ردیف AC-1.1.8 بدون تغییر ماند و شواهد بر اساس Contract v1.1 ثبت شد.
- دامنه این بستن: فقط ثبت Acceptance اداری/مهندسی با شواهد موجود — بدون هیچ کد/طراحی/refinement جدید و بدون تغییر متن ACها. بستن رسمی G3 خارج از دامنه T-1.1.6 است (تصمیم PM+QA/PO).
```

## WP-1.2 / WP-1.3

```text
WP-1.2 (S1 & Integrity Hardening)  — ACها در زمان decompose (پس از acceptance WP-1.1) به همین Register افزوده می‌شوند.
WP-1.3 (Retention & Recovery)      — ACها در زمان decompose؛ مقادیر سیاست pending DEF4.
```

## WP-2.1 — Page Ordering & Artifact Reconstruction (decomposed 2026-10-01 — پس از G3)

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-2.1.1 | WP-2.1 | برای هر capture COMPLETED، یک Document با پیوند صریح capture_id/S1 ایجاد و دائمی ذخیره می‌شود و پس از restart قابل بازیابی است | اجرای تست ایجاد/بازیابی با گام restart | گزارش تست + رکورد بازیابی‌شده | T-2.1.2 | Document/Page Store Component | kandoo/src/reconstruction/tests/test_recon_service.py::test_reconstruct_from_completed_capture_builds_document_with_ordered_pages + test_reconstruct_is_idempotent_per_capture_inv_r11؛ restart: kandoo/src/reconstruction/tests/test_recon_store.py::test_documents_and_pages_are_durable_across_restart + test_recon_e2e.py::test_full_reconstruction_mvp_journey (گام‌های ۱ و ۵) + kandoo/src/run_smoke_reconstruction.py (گام‌های ۲ و ۵) | PASS | TM acceptance via WP-2.1-IMPL / 2026-10-01 |
| AC-2.1.2 | WP-2.1 | page ordering قطعی و بازتولیدپذیر است: همان ورودی → همان ترتیب صفحات (بدون heuristic معنایی) | deterministic ordering test | گزارش تست ترتیب | T-2.1.3 | Reconstruction Service | kandoo/src/reconstruction/tests/test_recon_pages.py (۸ تست: test_derivation_is_deterministic_pure_function_of_bytes + test_aggregate_artifact_derives_original_parts_in_order + fallback قطعی) + kandoo/src/reconstruction/tests/test_recon_service.py::test_ordering_is_deterministic_and_bound_to_input_order + test_recon_e2e.py::test_full_reconstruction_mvp_journey (گام ۳) | PASS | TM acceptance via WP-2.1-IMPL / 2026-10-01 |
| AC-2.1.3 | WP-2.1 | هر page به منبع خود پیوند دارد و هیچ داده فاکتوری استخراج/حدس زده نمی‌شود (فقط ساختار) | تست پیوند + مرز no-extraction (بازرسی ساختاری) | گزارش تست پیوند page→capture_id/S1 | T-2.1.3 | Reconstruction Service | kandoo/src/reconstruction/tests/test_recon_service.py::test_structural_no_extraction_boundary_model_and_read_surface (فیلدست‌های دقیق مدل + ستون‌های store + خروجی read) + test_byte_content_fidelity_pages_tile_capture_artifact_exactly (پیوند/وفاداری بایتی) + test_recon_e2e.py::test_no_interpretive_data_enters_the_reconstruction_path (محتوای فاکتورمانند → فقط bytes خام) | PASS | TM acceptance via WP-2.1-IMPL / 2026-10-01 |
| AC-2.1.4 | WP-2.1 | verify-on-read فعال است: سند/page دستکاری‌شده → fail صریح، بدون خواندن ساکتِ خراب | corruption injection test | گزارش تست fail/pass | T-2.1.2, T-2.1.3 | Reconstruction Verification | kandoo/src/reconstruction/tests/test_recon_read_path.py (۶ تست: test_tampered_page_fails_explicitly_and_never_delivers_content + test_document_fingerprint_mismatch_fails_explicitly + test_every_read_reverifies_no_caching_truthful_latest_result + test_read_refused_for_non_completed_or_unknown_documents) + kandoo/src/run_smoke_reconstruction.py (گام ۶) | PASS | TM acceptance via WP-2.1-IMPL / 2026-10-01 |
| AC-2.1.5 | WP-2.1 | ساخت نیمه‌تمام/قطع‌شده در شروع بعدی یا کامل یا صریحاً failed تسویه می‌شود؛ هیچ سند نیمه‌ساخت valid ارائه نمی‌شود | interruption injection test | گزارش تست سناریوی قطع | T-2.1.2, T-2.1.3 | Reconstruction Recovery | kandoo/src/reconstruction/tests/test_recon_recovery.py (۷ تست: test_record_without_pages_settles_pages_missing_incomplete + test_interrupted_construction_with_all_pages_completes_at_recovery + test_corrupted_page_in_residue_settles_verify_failed + test_unknown_fingerprint_algorithm_is_conservative_never_completed + uniqueness-loser + idempotence + mixed) + kandoo/src/run_smoke_reconstruction.py (گام ۵) | PASS | TM acceptance via WP-2.1-IMPL / 2026-10-01 |
| AC-2.1.6 | WP-2.1 | فیلدهای traceability (document_id، پیوند capture_id/S1، timestampها) در هر سند حاضرند | بازرسی schema سند + تست | نمونه سند + جدول فیلدها | T-2.1.1, T-2.1.4 | Reconstruction Contract + تست تجمیعی | kandoo/specs/WP-2.1-reconstruction-contract.md (§2/§3/§9 نگاشت AC) + kandoo/src/reconstruction/tests/test_recon_store.py::test_create_active_document_roundtrip_with_full_traceability + kandoo/src/reconstruction/tests/test_recon_e2e.py::test_full_reconstruction_mvp_journey (گام ۹ sweep: document_id + capture_id/S1 + created_at + integrity_verified_at روی سند نهایی) | PASS | TM acceptance via WP-2.1-IMPL / 2026-10-01 |

```text
WP-2.1 Acceptance Status: 6/6 closed — WP-2.1: IMPLEMENTED (2026-10-01, dispatch یکپارچه WP-2.1-IMPL)
Note (2026-10-01, WP-2.1-IMPL) — ACCEPTANCE CLOSURE (WP-2.1):
- اجرای واقعی با کد (بدون چرخه مدیریتی جدید، طبق dispatch TM): Contract حداقلی inline (T-2.1.1) + Store + Service + Recovery + Smoke.
- بازاجرای زنده همین روز: pytest kandoo/src/capture/tests kandoo/src/reconstruction/tests → 101/101 PASSED (0.75s؛ Python 3.12.14 / pytest 9.0.2) | kandoo/src/run_smoke_reconstruction.py → SMOKE OK (۷ گام) | kandoo/src/run_smoke.py → SMOKE OK (رجرسیون WP-1.1).
- الگوی نام‌گذاری تست‌های لایه Reconstruction با پیشوند test_recon_ است تا collection هم‌زمان دو suite تداخلی نداشته باشد؛ یک اصلاح زیرساختی در bootstrap مسیر test (conftest لایه capture) انجام شد — هیچ رفتار Frozen تغییر نکرده است.
- مرز اعلامی: هیچ OCR/VLM/Extraction/Normalization/S2/dedup سند در این لایه اجرا نشده است (تست ساختاری AC-2.1.3). هویت سند = document_id محلی؛ حل هویت سند همچنان P7 (D-02).
```

## WP-2.2 — Reconstruction Evidence (decomposed + implemented 2026-10-01 — dispatch یکپارچه WP-2.2-IMPL به دستور TM)

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-2.2.1 | WP-2.2 | برای هر reconstruct نهایی یک evidence record دائمی با پیوند document_id/capture_id/capture_s1 ثبت و پس از restart قابل خواندن است | تست دوام + restart | گزارش تست + رکورد evidence بازیابی‌شده | T-2.2.2 | Evidence Store Component | kandoo/src/reconstruction/tests/test_evidence_store.py::test_document_completed_event_binds_document_and_capture + test_events_are_durable_across_restart + test_unknown_document_evidence_read_is_refused + kandoo/src/run_smoke_evidence.py (گام ۴) | PASS | TM acceptance via WP-2.2-IMPL / 2026-10-01 |
| AC-2.2.2 | WP-2.2 | DOCUMENT_COMPLETED حاوی binding page_index → بازه بایتی منبع است؛ هر بازه بایت‌به‌بایت با محتوای page ذخیره‌شده و fingerprint آن برابر است و بازه‌ها artifact را دقیقاً tile می‌کنند (هر دو فرمت: aggregate و fallback) | binding fidelity test | گزارش تست slice==page + پوشش کامل | T-2.2.2 | Evidence Binding | kandoo/src/reconstruction/tests/test_evidence_binding.py::test_completed_event_page_spans_tile_the_aggregate_artifact + test_span_slices_equal_durable_page_bytes_and_fingerprints + test_single_page_fallback_span_covers_whole_artifact + test_recovery_settlement_completed_event_carries_spans + kandoo/src/run_smoke_evidence.py (گام ۳) | PASS | TM acceptance via WP-2.2-IMPL / 2026-10-01 |
| AC-2.2.3 | WP-2.2 | evidence ضد دستکاری است: جهش فیلد، حذف ردیف انتهایی (truncation)، حذف لنگر head، درج رکورد جعلی → fail صریح در خواندن بعدی؛ هیچ خواندن ساکتِ خرابِ evidence وجود ندارد؛ زنجیره تحت همروندی دقیق می‌ماند | tamper matrix + concurrency test | گزارش تست fail صریح برای هر بردار دستکاری | T-2.2.2 | Evidence Chain Integrity | kandoo/src/reconstruction/tests/test_evidence_chain.py (۸ تست: test_record_field_tamper_is_detected_explicitly + test_row_deletion_truncation_is_detected_explicitly + test_head_anchor_deletion_is_detected_explicitly + test_forged_row_insertion_is_detected_explicitly + test_concurrent_appends_produce_exact_contiguous_chain + test_genesis_and_chain_links_are_correct + test_verify_chain_whole_log_audit_states) + kandoo/src/run_smoke_evidence.py (گام ۶) | PASS | TM acceptance via WP-2.2-IMPL / 2026-10-01 |
| AC-2.2.4 | WP-2.2 | evidence فقط داده ساختاری حمل می‌کند (کلیدهای payload مجاز ثابت per event_type)؛ هیچ محتوا یا داده تفسیری وارد evidence نمی‌شود | تست ساختاری + رفتاری | گزارش تست کلیدها + عدم حضور محتوا | T-2.2.1, T-2.2.2 | Evidence Contract + تست مرز | kandoo/specs/WP-2.2-reconstruction-evidence-contract.md (§1/§3 مرز + کلیدهای مجاز) + kandoo/src/reconstruction/tests/test_evidence_e2e.py::test_structural_no_content_boundary_in_evidence (کلیدها ⊆ مجاز + نبود fragments محتوا در همه ستون‌ها) + test_evidence_store.py::test_event_vocabulary_and_payload_keys_are_enforced | PASS | TM acceptance via WP-2.2-IMPL / 2026-10-01 |
| AC-2.2.5 | WP-2.2 | شکست evidence رفتار و outcomeهای Reconstruction را تغییر نمی‌دهد و هرگز ساکت نیست (issue surfacing)؛ رگرسیون کامل WP-2.1/WP-1.1 سبز می‌ماند | non-intrusive failure test + رگرسیون کامل | گزارش تست outcomeهای بدون تغییر + issues صریح + 101/101 رگرسیون | T-2.2.2 | Non-intrusive Recorder | kandoo/src/reconstruction/tests/test_evidence_chain.py::test_evidence_failure_never_alters_reconstruction_outcomes (ReconstructCompleted/ReadSuccess/AlreadyExists بدون تغییر + issues + recovery complete) + رگرسیون زنده: pytest kandoo/src/capture/tests kandoo/src/reconstruction/tests → 126/126 PASSED (101 قلم Frozen سبز) | PASS | TM acceptance via WP-2.2-IMPL / 2026-10-01 |
| AC-2.2.6 | WP-2.2 | رویدادهای lifecycle واقعی (build/settle/verified-read/recovery-settled) فقط-الحاقی با seq صعودی و timestamp ثبت می‌شوند؛ ترتیب با ترتیب واقعی وقوع سازگار است | event trail test | گزارش تست ترتیب رویدادها | T-2.2.2 | Evidence Event Trail | kandoo/src/reconstruction/tests/test_evidence_binding.py::test_verified_read_verdicts_are_recorded_in_order (COMPLETED→VALID→FAILED) + test_settled_failure_outcome_is_evidenced (D-1 واقعی: SETTLED_FAILED→REFUSED) + test_recovery_settlement_failed_event_recorded_without_spans + test_evidence_e2e.py::test_full_path_capture_to_verified_evidence_chain_across_restart + test_evidence_store.py::test_append_only_no_update_or_delete_paths_exist (فقط-الحاقی ساختاری) | PASS | TM acceptance via WP-2.2-IMPL / 2026-10-01 |

```text
WP-2.2 Acceptance Status: 6/6 closed — WP-2.2: IMPLEMENTED (2026-10-01, dispatch یکپارچه WP-2.2-IMPL)
Note (2026-10-01, WP-2.2-IMPL) — ACCEPTANCE CLOSURE (WP-2.2):
- تعیین Task بعدی Critical Path (طبق dispatch TM: «ابتدا Registerها را بخوان»): تنها قلم باقی‌مانده فاز P2 در Phase Index = WP-2.2 Reconstruction Evidence؛ P3 هنوز در مسیر نرسیده (قاعده ۸ dispatch).
- اجرای واقعی با کد (بدون فاز طراحی/Review جدید، طبق dispatch TM): Contract حداقلی inline (T-2.2.1) + Evidence Store append-only با زنجیره هش و لنگر head + binding بازه بایتی page→منبع + verified evidence read + اتصال غیرمخرب به service/recovery.
- بازاجرای زنده همین روز: pytest kandoo/src/capture/tests kandoo/src/reconstruction/tests → 126/126 PASSED (0.98s؛ Python 3.12.14 / pytest 9.0.2؛ شامل 25 تست جدید evidence + 101 رگرسیون Frozen) | kandoo/src/run_smoke_evidence.py → SMOKE OK (۶ گام) | kandoo/src/run_smoke_reconstruction.py → SMOKE OK (رجرسیون WP-2.1) | kandoo/src/run_smoke.py → SMOKE OK (رجرسیون WP-1.1).
- انتخاب‌های delegated اعلامی (D-09 — OD-E1..OD-E6 در Contract §1/§4/§5/§7 و گزارش T-2.2.2): SQLite stdlib فایل مجزا؛ زنجیره sha256-v1 (genesis 0×64) + لنگر evidence_head هم‌تراکنش برای کشف truncation؛ spans مشتق قطعی از وضعیت durable؛ recorder غیرمخرب با issue surfacing؛ ساعت واحد لایه.
- مرز اعلامی: هیچ Extraction/OCR/VLM/Normalization/S2/dedup سند اجرا نشده؛ evidence هیچ محتوایی حمل نمی‌کند (تست ساختاری AC-2.2.4)؛ رفتار Frozen WP-2.1/WP-1.1 دست‌نخورده (126/126 شامل رگرسیون کامل).
- Gate فاز P2 هنوز بسته نشده است (تصمیم PM+QA/PO)؛ هر دو WP فاز P2 اکنون IMPLEMENTED‌اند.
```

## WP-3.1 — Engine-Agnostic Extraction Pipeline (decomposed + implemented 2026-10-01 — dispatch یکپارچه WP-3.1-IMPL به دستور TM: «وارد P3 شو؛ decomposition فقط به اندازه لازم و inline»)

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-3.1.1 | WP-3.1 | برای هر سند تأییدشده، extraction یک record ساختاریافته دائمی با پیوند صریح document_id/capture_id/capture_s1 تولید می‌کند و پس از restart قابل خواندن است | تست traceability + durability/restart | گزارش تست + رکورد بازیابی‌شده | T-3.1.2 | Extraction Store + Service | kandoo/src/extraction/tests/test_ext_service.py::test_happy_path_extract_completes_with_traceability_and_verbatim_fields + kandoo/src/extraction/tests/test_ext_store.py::test_commit_and_get_roundtrip_carries_full_traceability + test_records_are_durable_across_restart + kandoo/src/extraction/tests/test_ext_e2e.py::test_full_extraction_mvp_journey_across_restart (گام‌های ۱ و ۵) + kandoo/src/run_smoke_extraction.py (گام‌های ۲ و ۵) | PASS | TM acceptance via WP-3.1-IMPL / 2026-10-01 |
| AC-3.1.2 | WP-3.1 | pipeline موتور-آگنوستیک است: موتورها پشت interface یکسان تعویض می‌شوند؛ خروجی موتور پیش از persistence اعتبارسنجی می‌شود؛ موتور ناشناس → outcome صریح | تست چند-موتوره + ماتریس violation | گزارش تست stub engine + ۶ بردار fail-closed | T-3.1.1, T-3.1.2 | Engine Abstraction + Validation | kandoo/src/extraction/tests/test_ext_service.py::test_second_engine_same_document_yields_a_separate_record_engine_agnostic + test_unknown_engine_is_explicit_and_persists_nothing + test_engine_contract_violations_fail_closed_before_persistence (۶ بردار parametric) + test_engine_output_must_not_reference_pages_it_was_not_given + kandoo/src/extraction/tests/test_ext_e2e.py::test_full_extraction_mvp_journey_across_restart (گام ۴) | PASS | TM acceptance via WP-3.1-IMPL / 2026-10-01 |
| AC-3.1.3 | WP-3.1 | هر فیلد استخراج‌شده به منبع خود پیوند دارد: page_index + بازه بایتی + page_fingerprint؛ value_verbatim دقیقاً برابر decoding بایت‌های بازه است (بدون هیچ تبدیل) | verbatim span binding test | گزارش تست slice decode == value | T-3.1.2 | Verbatim Span Binding | kandoo/src/extraction/tests/test_ext_engine.py::test_fields_are_verbatim_and_spans_point_at_exact_value_bytes + test_page_index_binding_and_multi_page_field_order + kandoo/src/extraction/tests/test_ext_service.py::test_happy_path_extract_completes_with_traceability_and_verbatim_fields (حلقه span fidelity) + kandoo/src/extraction/tests/test_ext_e2e.py::test_full_extraction_mvp_journey_across_restart (گام ۳ — slicing خود artifact منبع) + kandoo/src/run_smoke_extraction.py (گام ۳) | PASS | TM acceptance via WP-3.1-IMPL / 2026-10-01 |
| AC-3.1.4 | WP-3.1 | idempotency سطح Extraction: همان (document_id, engine_id, engine_schema_version) → دقیقاً یک record؛ replay صریح؛ موتور/schema دیگر → record جدا | INV-X-1:1 test + index backstop | گزارش تست replay + چند-موتور | T-3.1.2 | INV-X-1:1 Uniqueness | kandoo/src/extraction/tests/test_ext_service.py::test_reextract_same_triple_is_idempotent_already_exists_never_second_record + kandoo/src/extraction/tests/test_ext_store.py::test_inv_x11_same_triple_commit_raises_duplicate_with_index_backstop + test_different_engine_or_schema_version_is_a_separate_record + kandoo/src/run_smoke_extraction.py (گام ۴) | PASS | TM acceptance via WP-3.1-IMPL / 2026-10-01 |
| AC-3.1.5 | WP-3.1 | verified extraction read فعال است: record/field دستکاری‌شده → fail صریح بدون تحویل محتوا؛ همه outcomeها صریح‌اند (source/refused/engine failure/contract violation/storage) | tamper matrix + explicit-outcome tests | گزارش تست fail صریح برای هر بردار | T-3.1.2 | Verified Extraction Read | kandoo/src/extraction/tests/test_ext_read_path.py (۵ تست: test_tampered_field_value_fails_explicitly_and_never_delivers + test_tampered_record_scalar_fails_explicitly + test_deleted_field_row_is_detected_explicitly + test_unknown_extraction_id_is_refused + healthy read) + kandoo/src/extraction/tests/test_ext_service.py::test_engine_failure_surfaces_explicitly_and_persists_nothing + test_unexpected_engine_exception_is_surfed_explicitly + test_source_refused_for_unknown_document + test_source_integrity_failure_on_tampered_document_persists_nothing + kandoo/src/run_smoke_extraction.py (گام ۶) | PASS | TM acceptance via WP-3.1-IMPL / 2026-10-01 |
| AC-3.1.6 | WP-3.1 | مرز: هیچ داده normalization/canonicalization/validation/invoice در مدل/store/outcomes نیست؛ provenance فقط EXTRACTED (واژگان D-01)؛ رفتار Frozen WP-1.1/WP-2.1/WP-2.2 دست‌نخورده | تست ساختاری مرز + رگرسیون کامل | گزارش تست field-sets/columns + 126/126 رگرسیون Frozen | T-3.1.1, T-3.1.2, T-3.1.3 | Boundary Enforcement | kandoo/src/extraction/tests/test_ext_e2e.py::test_structural_boundary_no_normalization_canonical_or_validation_datum (field-sets دقیق مدل + ستون‌های store + EXTRACTED-only rows + verbatim مجدد) + kandoo/src/extraction/tests/test_ext_store.py::test_storage_level_provenance_gate_blocks_non_extracted + test_commit_refuses_non_extracted_provenance_defensively + kandoo/src/extraction/tests/test_ext_service.py::test_service_takes_no_capture_access_and_no_raw_artifact_path (قاعده ۸ dispatch) + رگرسیون زنده: 126/126 Frozen سبز | PASS | TM acceptance via WP-3.1-IMPL / 2026-10-01 |

```text
WP-3.1 Acceptance Status: 6/6 closed — WP-3.1: IMPLEMENTED (2026-10-01, dispatch یکپارچه WP-3.1-IMPL)
Note (2026-10-01, WP-3.1-IMPL) — ACCEPTANCE CLOSURE (WP-3.1):
- تعیین WP بعدی Critical Path (طبق dispatch TM: «ابتدا Registerها را بخوان»): Phase Index = WP-3.1 Engine-Agnostic Extraction Pipeline (اولین قلم P3)؛ decomposition به‌صورت inline انجام شد (T-3.1.1..T-3.1.3) و بلافاصله ساخت واقعی آغاز گردید — بدون فاز طراحی/Review جدید.
- اجرای واقعی با کد: ExtractionInput (پروجکشن extraction-ready فقط از DocumentReadSuccess) → ExtractionEngine ABC قابل‌تعویض + ReferenceDelimitedEngine (grammar اعلان‌شده key=value بر UTF-8 strict) → اعتبارسنجی قرارداد C1..C5 (fail-closed) → commit اتمیک → verified read با record_fingerprint.
- بازاجرای زنده همین روز: pytest kandoo/src/capture/tests kandoo/src/reconstruction/tests kandoo/src/extraction/tests → 164/164 PASSED (54 capture + 72 reconstruction + 38 extraction؛ Python 3.12.14 / pytest 9.0.2) | kandoo/src/run_smoke_extraction.py → SMOKE OK (۶ گام) | رگرسیون: run_smoke.py + run_smoke_reconstruction.py + run_smoke_evidence.py → هر سه SMOKE OK.
- انتخاب‌های delegated اعلامی (D-09 — OD-X1..OD-X8 در store.py و Contract §1/§4/§8): SQLite stdlib فایل مجزا؛ commit اتمیک record+fields (صفر residue — بدون recovery sweep به‌سازه)؛ INV-X-1:1 با UNIQUE index؛ record_fingerprint sha256-v1 (reuse S1Service)؛ CHECK سطح storage فقط EXTRACTED؛ ساعت واحد لایه؛ بدون مسیر UPDATE/DELETE. ReferenceDelimitedEngine = موتور مرجع برای اجراپذیری MVP، نه انتخاب موتور محصول (OCR/VLM deferred طبق D-09 — abstraction قابل‌تعویض باقی است).
- مرز اعلامی: هیچ Normalization/Canonicalization/Validation/Invoice/S2/dedup در این لایه اجرا نشده (تست ساختاری AC-3.1.6)؛ توالی فیلدها هرگز dedup نمی‌شود؛ Extraction فقط از verified read تغذیه می‌شود (بدون تفسیر موازی artifact خام — تست ساختاری)؛ رفتار Frozen WP-1.1/WP-2.1/WP-2.2 دست‌نخورده (126/126 رگرسیون سبز).
- Gate فاز P3 بسته نشده است (تصمیم PM+QA/PO)؛ WP-3.2 Evidence Binding در انتظار decompose است (مصرف‌کننده extraction_ids_for_document + spans).
```

## WP-3.2 — Extraction Evidence Binding (decomposed + implemented 2026-10-01 — dispatch یکپارچه WP-3.2-IMPL به دستور TM: «بدون باز کردن WP-3.1 و بدون Design/Review جدید، مستقیماً WP-3.2 را اجرا کن»)

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-3.2.1 | WP-3.2 | برای هر extraction record، bind فقط زمانی ایجاد می‌شود که هر پنج حلقه زنجیره در لحظه bind راستی‌آزمایی شود (verified extraction read + fresh verified document read با تطبیق linkage + verified evidence read با anchor DOCUMENT_COMPLETED + span fidelity کامل)؛ replay صریح با همان binding_id (INV-B-1:1)؛ همه outcomeها صریح‌اند | whole-chain bind test + replay test + explicit-outcome matrix | گزارش تست BindingCompleted + BindingAlreadyExists + ماتریس رد شدن | T-3.2.1, T-3.2.2 | Extraction Binding Store + Binder | kandoo/src/extraction/tests/test_binding_core.py::test_bind_creates_durable_binding_with_full_chain + test_binding_replay_is_explicit_idempotent + test_bind_refused_for_unknown_extraction + test_bind_fails_closed_when_extraction_tampered + test_bind_fails_closed_when_document_tampered + test_bind_refused_without_reconstruction_evidence + kandoo/src/extraction/tests/test_binding_durability.py::test_zero_residue_after_refused_bind + kandoo/src/run_smoke_binding.py (گام‌های ۱ و ۲) | PASS | TM acceptance via WP-3.2-IMPL / 2026-10-01 |
| AC-3.2.2 | WP-3.2 | هر extracted field از طریق binding به Document/Page (page_index + page_fingerprint) و span دقیق منبع (byte_start, byte_end) حل می‌شود؛ مسیر کامل field → page → artifact span (evidence WP-2.2) → capture S1 ماشین‌چک‌پذیر است؛ enumeration سند-محور دقیق و بدون fabrication است | full provenance walk test + enumeration test | گزارش تست walk چهار حلقه‌ای + bindings_for_document | T-3.2.1, T-3.2.2 | Per-Field Provable Traceability | kandoo/src/extraction/tests/test_binding_core.py::test_per_field_traceability_walk_field_to_capture (entry→page slice decode + evidence page_spans fingerprint join + artifact slice == page bytes + capture_s1 equality) + test_bindings_for_document_enumeration (دو سند × دو موتور، ترتیب قطعی) + kandoo/src/run_smoke_binding.py (گام ۳ و ۴) | PASS | TM acceptance via WP-3.2-IMPL / 2026-10-01 |
| AC-3.2.3 | WP-3.2 | verified binding read (VOR) همه حلقه‌ها را داخل خود read بازررسی می‌کند: binding log (head anchor + chain + fingerprint)، extraction record (+ برابری fingerprint لنگر‌شده)، fresh document read، evidence anchor (seq/record_hash)، span fidelity (entry↔field↔slice decode)؛ هر شکست → BindingReadIntegrityFailure با attribution قطعی یکی از پنج BindingLink و بدون تحویل entries؛ NO_VERDICT → VerificationUnavailable با Issue-Report | tamper matrix ۸ بردار + content-free assertion + NO_VERDICT test | گزارش تست link attribution برای هر بردار | T-3.2.1, T-3.2.2 | Verified Binding Read | kandoo/src/extraction/tests/test_binding_read_path.py (۱۵ تست): BINDING (test_tamper_binding_entry_offset/scalar/field_name + test_delete_binding_tail_row — truncation guard قبل از refusal)؛ EXTRACTION (test_tamper_extraction_value + test_delete_extraction_record — حذف bound extraction قابل اثبات است)؛ EVIDENCE (test_tamper_reconstruction_evidence + test_evidence_anchor_drift)؛ DOCUMENT (test_tamper_document_page_content + test_delete_document_pages_store_defect_read_unavailable)؛ SPAN (test_coherent_page_forgery — جعل هماهنگ fingerprintها که verified read را عبور می‌کند)؛ NO_VERDICT (test_unverifiable_fingerprint_algorithm) + content-free assertion در _assert_integrity_failure + kandoo/src/run_smoke_binding.py (گام‌های ۶، ۷، ۸) | PASS | TM acceptance via WP-3.2-IMPL / 2026-10-01 |
| AC-3.2.4 | WP-3.2 | durability/restart (synchronous=FULL، append-only، بدون UPDATE/DELETE)؛ tamper-evident بودن log خود binding (hash chain + head anchor → حذف دم/جعل میانی/جعل هماهنگ کشف می‌شود)؛ idempotency؛ مرز: payload فقط ساختاری (بدون هیچ value)، payload Frozen layers دست‌نخورده (رگرسیون کامل سبز) | restart test + chain audit tests + concurrency + structural boundary tests + full regression | گزارش تست restart/audit/8-thread + 200/200 رگرسیون | T-3.2.1, T-3.2.2, T-3.2.3 | Durability + Tamper Evidence + Boundary | kandoo/src/extraction/tests/test_binding_durability.py (۵ تست: test_restart_preserves_bindings_and_reverifies_everything + test_chain_audit_detects_tail_deletion + test_chain_audit_detects_mid_log_forgery + test_zero_residue_after_refused_bind + test_concurrent_bind_appends_are_exact — ۸ thread اتصال مستقل) + kandoo/src/extraction/tests/test_binding_boundary.py (۶ تست: test_binding_record_field_sets_are_exact + test_binding_payload_carries_no_values + test_binding_store_schema_has_no_value_column + test_read_success_outcome_shape_is_exact + test_no_update_or_delete_path_in_binding_api + test_binding_operations_leave_frozen_layers_verified) + رگرسیون زنده: 200/200 (164 Frozen شامل) | PASS | TM acceptance via WP-3.2-IMPL / 2026-10-01 |

```text
WP-3.2 Acceptance Status: 4/4 closed — WP-3.2: IMPLEMENTED (2026-10-01, dispatch یکپارچه WP-3.2-IMPL)
Note (2026-10-01, WP-3.2-IMPL) — ACCEPTANCE CLOSURE (WP-3.2):
- Scope (inline، طبق dispatch TM قاعده ۱–۲): SPEC-WP32-EVB v1.0-MVP (kandoo/specs/WP-3.2-evidence-binding-contract.md) — «verified extraction record → durable, tamper-evident Extraction Evidence Binding → per-field provable traceability». هیچ چرخه Contract/Architecture Review جدید ایجاد نشد.
- اجرای واقعی با کد: ExtractionBindingStore (فایل DB مجزا، append-only، commit اتمیک binding+entries، INV-B-1:1، binding_fingerprint sha256-v1 روی canonical bytes، hash chain + head anchor به الگوی WP-2.2) + ExtractionEvidenceBinder (bind_extraction با راستی‌آزمایی هر ۵ حلقه در لحظه bind؛ read_binding با VOR پنج‌حلقه‌ای و attribution قطعی BindingLink: binding|extraction|document|evidence|span؛ bindings_for_document؛ verify_chain؛ issue_reports). صفر تغییر در کد Frozen WP-1.1/WP-2.1/WP-2.2/WP-3.1 — فقط مصرف read-only از interfaceهای verified-read موجود (قاعده ۶ و ۹ dispatch).
- جمع‌بندی شواهد: 36/36 تست Binding جدید + 164/164 رگرسیون Frozen = 200/200 PASSED (Python 3.12.14 / pytest 9.0.2) + run_smoke_binding.py SMOKE OK (۸ گام: bind/walk/idempotency/restart/forgery/tamper×2) + ۴ Smoke قبلی SMOKE OK.
- جعل هماهنگ کشف می‌شود: tamper صفحه + محاسبه مجدد page_fingerprint و document_fingerprint (verified read را عبور می‌کند) در gate SPAN لایه binding رد می‌شود — چون span لنگرشده دیگر به value verbatim decode نمی‌شود. حذف bound extraction/extracion record/evidence نیز در حلقه مربوطه صریحاً FAIL می‌شود (هدف اثباتی binding).
- مرز اعلامی: binding entries فقط ساختاری‌اند (بدون value_verbatim/value_encoding — تست ساختاری OD-B7)؛ هیچ داده Normalization/Canonicalization/Validation وارد نشده؛ Evidence Reconstruction فقط read-only مصرف شد (هیچ event جدید به vocabulary فروزن WP-2.2 اضافه نشد)؛ رگرسیون کامل 200/200 سبز.
- Gate فاز P3 بسته نشده است (تصمیم PM+QA/PO). هر دو WP فاز P3 (WP-3.1 + WP-3.2) اکنون IMPLEMENTED‌اند.
```

## WP-4.1 — Normalization Rules (decomposed + implemented 2026-10-01 — dispatch یکپارچه WP-4.1-IMPL به دستور TM: «Implement P4 — Normalization؛ فقط فایل‌های لازم»)

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-4.1.1 | WP-4.1 | نرمال‌سازی قطعی per-field با نگاشت TOTAL positional (هیچ فیلدی skip یا جعل نمی‌شود؛ counts reconciled)؛ statuses/reasons صریح (NORMALIZED/DEFERRED/REJECTED)؛ خروجی محتوایی تابع خالص ورودی+نسخه ruleset؛ provenance فقط EXTRACTED (relay D-01) | rule matrix tests + total-mapping test + determinism test | گزارش تست وضعیت‌ها + شمارنده‌ها + قطعیت | T-4.1.1, T-4.1.2 | Rules + Service | kandoo/src/normalization/tests/test_norm_rules.py (۳۱ تست: ماتریس عددی ۱۴+۱۰ بردار، NFC/trim، control gate، date ISO، purity) + test_norm_service.py::test_happy_path_total_mapping_with_statuses_and_counts + test_missing_field_is_never_invented + test_whitespace_only_field_surfaces_as_deferred_in_pipeline + test_normalized_content_determinism_same_content_two_ruleset_registrations + kandoo/src/run_smoke_normalization.py (گام ۳ و ۶) | PASS | TM acceptance via WP-4.1-IMPL / 2026-10-01 |
| AC-4.1.2 | WP-4.1 | traceability ماشین‌چک‌پذیر هر normalized field تا source: (extraction_id, field_seq) → value_verbatim → binding WP-3.2 → Document/Page/span → Capture S1؛ تضمین‌های binding/evidence پس از ترافیک normalization دست‌نخورده؛ بدون کپی span/content | provenance walk test + frozen-layers-verified test | گزارش تست walk کامل + برابری S1 | T-4.1.2, T-4.1.3 | Per-Field Traceability | kandoo/src/normalization/tests/test_norm_e2e.py::test_machine_checkable_provenance_walk_normalized_to_capture + test_norm_boundary.py::test_normalization_leaves_all_frozen_layers_verified + test_no_span_or_content_duplication_in_normalized_model + kandoo/src/run_smoke_normalization.py (گام ۴ و ۷) | PASS | TM acceptance via WP-4.1-IMPL / 2026-10-01 |
| AC-4.1.3 | WP-4.1 | persistence طبق الگوی پروژه: SQLite فایل مجزا synchronous=FULL، commit اتمیک record+fields (صفر residue)، INV-N-1:1 با replay صریح، ruleset/نسخه دیگر → record جدا، بدون UPDATE/DELETE، verified read (VOR) با fingerprint sha256-v1، restart-safe، tamper → fail صریح بدون تحویل محتوا | durability/restart tests + VOR tamper matrix + storage-gate tests | گزارش تست restart/audit/gates + 284/284 رگرسیون | T-4.1.2, T-4.1.3 | Durable Store + VOR Read | kandoo/src/normalization/tests/test_norm_durability.py (۸ تست: restart/idempotency/gates/no-update-delete/zero-residue) + test_norm_read_path.py (۷ تست: tamper value/scalar/status-gate/row-deletion/NO_VERDICT/refused) + test_norm_service.py::test_inv_n11_replay_is_explicit_and_never_second_record + test_different_ruleset_version_is_a_separate_record + test_unknown_ruleset_is_explicit_and_persists_nothing + test_tampered_extraction_fails_closed_and_persists_nothing + kandoo/src/run_smoke_normalization.py (گام ۵، ۷، ۸) | PASS | TM acceptance via WP-4.1-IMPL / 2026-10-01 |
| AC-4.1.4 | WP-4.1 | مرز: هیچ datum کانونی/هویتی/business در مدل/store/outcomes نیست (نام فیلد فقط relay می‌شود)؛ مستقل از موتور extraction (import صفر از engineها؛ هم‌ارزی خروجی دو موتور)؛ DERIVED/UNRESOLVED تولید نمی‌شود؛ رفتار Frozen P1/P2/P3 دست‌نخورده | structural boundary tests + engine-equivalence test + full regression | گزارش تست field-sets/columns + stub equivalence + 284/284 رگرسیون کامل | T-4.1.1, T-4.1.2, T-4.1.3 | Boundary Enforcement | kandoo/src/normalization/tests/test_norm_boundary.py (۸ تست: test_normalized_field_field_set_is_exact + test_normalization_record_field_set_is_exact + test_store_schema_carries_no_canonical_or_business_columns + test_status_vocabulary_is_exactly_the_declared_three) + test_norm_service.py::test_normalization_is_engine_independent + test_norm_rules.py::test_provenance_is_relayed_verbatim_and_field_seq_mirrored + رگرسیون زنده: pytest capture/tests reconstruction/tests extraction/tests normalization/tests → 284/284 PASSED (200 Frozen سبز) | PASS | TM acceptance via WP-4.1-IMPL / 2026-10-01 |

```text
WP-4.1 Acceptance Status: 4/4 closed — WP-4.1: IMPLEMENTED (2026-10-01, dispatch یکپارچه WP-4.1-IMPL)
Note (2026-10-01, WP-4.1-IMPL) — ACCEPTANCE CLOSURE (WP-4.1):
- Scope (inline، طبق dispatch TM قواعد ۱–۲): SPEC-WP41-NORM v1.0-MVP (kandoo/specs/WP-4.1-normalization-contract.md) — «verified Extraction output → deterministic Normalized structured data». هیچ Design/Review جدید ایجاد نشد.
- اجرای واقعی با کد: NormalizationRuleSet seam + ReferenceNormalizationRulesV1 (control gate → NFC → trim → kind rule؛ kinds text/decimal/date؛ kind_profile اعلانی + fallback) + NormalizationStore (فایل DB مجزا، commit اتمیک، INV-N-1:1، fingerprint sha256-v1، بدون UPDATE/DELETE) + NormalizationService (normalize با VOR source read، read_normalization VOR، enumeration، issue_reports). اعداد کانونی STRING (بدون float)؛ حفظ ارقام اعشار؛ ابهام → DEFER صریح.
- جمع‌بندی شواهد: 84/84 تست P4 + 200/200 رگرسیون Frozen = 284/284 PASSED (Python 3.12.14 / pytest 9.0.2) + run_smoke_normalization.py SMOKE OK (۸ گام: extract/bind/normalize/provenance walk/idempotency/rejection/restart/tamper) + ۵ Smoke قبلی SMOKE OK.
- تصمیم‌های delegated اعلامی (D-09 — OD-N1..OD-N8 در Contract §9): SQLite stdlib فایل مجزا؛ commit اتمیک صفر residue؛ INV-N-1:1 + UNIQUE backstop؛ uuid4 + ساعت واحد لایه؛ fingerprint sha256-v1 reuse S1Service؛ CHECKهای سطح storage (provenance/status/value/reason)؛ بدون UPDATE/DELETE؛ ruleset مرجع = انتخاب اجراپذیری MVP.
- مرز اعلامی: هیچ Canonicalization/identity/fuzzy/business datum (تست ساختاری)؛ هیچ DERIVED/UNRESOLVED (WP-4.2/P5)؛ هیچ OCR/VLM/موتور جدید؛ مصرف extraction فقط از verified read (بدون مسیر موازی)؛ binding WP-3.2 فقط read-only در E2E؛ رگرسیون کامل 284/284 سبز.
- دو نکته شواهد: (۱) محتوای بایت‌یکسان دو بار capture نمی‌شود (D-03 Frozen — همین رفتار به‌عنوان probe قطعیت محتوا استفاده شد: دو ruleset هم‌گرامر روی یک extraction → مقادیر برابر)؛ (۲) یک تست اولیه (۱,۲۳ → DEFER) با grammar اعلان‌شده قرارداد ناسازگار بود و طبق قرارداد اصلاح شد (تک‌جداکننده با گروه ۲ رقمی = اعشار نامبهم).
- Gate فاز P4 بسته نشده است (تصمیم PM+QA/PO). WP-4.2 DERIVED Computation & Provenance در انتظار dispatch است.
Note (2026-10-05, WP-4.1-FREEZE-CORR) — PRE-FREEZE BOUNDARY CLARIFICATION (T-4.1.4):
- شفاف‌سازی قراردادی (بدون تغییر رفتار): SPEC-WP41-NORM §4.1 — DEFERRED صرفاً وضعیت لایهٔ Normalization است
  («تبدیل امن زیر grammar اعلان‌شده ممکن نیست → بدون تفسیر، بدون اختراع مقدار، عبور به جلو»)؛ DEFERRED ≠ UNRESOLVED؛
  WP-4.1 هرگز UNRESOLVED نمی‌سازد/نسبت نمی‌دهد/استنتاج/حل نمی‌کند. §4.2 — بدون محاسبهٔ DERIVED، بدون محاسبهٔ
  unit_amount از فیلدهای دیگر، بدون arithmetic معنایی بین فیلدها، بدون استنتاج مقادیر business جاافتاده؛
  DERIVED خارج از WP-4.1 باقی می‌ماند (WP-4.2).
- شواهد مرز (۸ تست جدید — test_norm_freeze_boundary.py): عدد مبهم (1.234، 12,345) / عدد ناقص (1.2.3، 12 EUR) /
  تاریخ پشتیبانی‌نشده (01.10.2026، 2026-02-30) → DEFERRED با reason اعلانی و هرگز UNRESOLVED | empty/whitespace-only
  → رفتار deferred اعلانی (empty-value) | sweep رکورد durable: هیچ datum UNRESOLVED (object/read/raw rows) |
  provenance همیشه EXTRACTED + رد ساختاری ردیف DERIVED/UNRESOLVED توسط storage gate | unit_amount=25 با
  quantity=4 و total.net=100.00 → «25» (ورودی خود فیلد؛ هرگز 25.00 حاصل 100/4) و بدون فیلد جعلی هنگام غیبت |
  خروجی‌های grammar اعلان‌شده دست‌نخورده (قطعیت رفتار 2026-10-01 حفظ شده).
- رگرسیون پس از اصلاح (اعداد واقعی اجرای 2026-10-05): P4.1 = 92/92 PASSED (84 قبلی + 8 مرزی)؛ رگرسیون کامل =
  292/292 PASSED (54 capture + 72 reconstruction + 38 extraction + 36 binding + 92 normalization)؛ SMOKE OK × ۶.
- هیچ قرارداد Frozen P1–P3 و هیچ تست موجودی حذف/تضعیف نشد؛ ۴/۴ AC تغییری در وضعیت ندارند (شواهد تقویت شد).
Note (2026-10-05, WP-4.1-FREEZE) — FORMAL FREEZE (T-4.1.5):
- WP-4.1 → **FROZEN** (2026-10-05) به دستور PO/TM؛ contradiction واقعی وجود نداشت. هیچ تغییر رفتاری در کد اعمال
  نشد (فقط Registerها/src/README.md)؛ شواهد قبلی (P4.1 92/92 + رگرسیون 292/292 + SMOKE OK × ۶) حفظ و در همان
  تاریخ مجدداً اجرا و تأیید شد.
- از این لحظه SPEC-WP41-NORM v1.0-MVP (+ §4.1 DEFERRED/UNRESOLVED و §4.2 مرز DERIVED) سند Frozen لایه
  Normalization است؛ هر تغییر آینده فقط از طریق ruleset/نسخه جدید از seam اعلان‌شده (بدون بازنویسی تاریخچه).
- Acceptance evidence بالادستی دست‌نخورده باقی می‌ماند (۴/۴ AC PASS — تاریخ‌ها و مکان‌های evidence تغییر نکردند).
```

## WP-4.2 — DERIVED Provenance & Exact Derivation Mechanism (implemented 2026-10-06 — dispatch اجرایی PO/TM: «BUILD واقعی»)

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-4.2.1 | WP-4.2 | derivation قطعی و دقیق: Formula Registry اعلانی/versioned/fingerprinted (داده نه کد؛ validation fail-closed؛ fingerprint sha256-v1 قطعی)؛ arithmetic دقیق بدون float و بدون rounding (ADD/SUB/MUL دقیق؛ DIV فقط terminating — غیردقیق → refusal صریح)؛ مثال مجاز MVP اجراشدنی (total.gross = net + tax)؛ فرمول version دیگر → derivation مجزا | formula tests + arithmetic tests + AST no-float scan | گزارش تست exactness/determinism/division-refusal | T-4.2.1, T-4.2.2, T-4.2.3 | Formula Registry + Exact Engine | test_deriv_formulas.py (۱۹ تست: validation/fingerprint/version) + test_deriv_arithmetic.py (۱۶ تست: 0.1+0.2=«0.3»، دقت >2^53، DIV 1/3 → NonExactResult، خروجی کانونی) + test_deriv_service.py (v2 → record مجزا؛ دو فرمول هم‌record) + test_deriv_boundary.py (AST: صفر float literal/call) | PASS | TM acceptance via WP-4.2-IMPL / 2026-10-06 |
| AC-4.2.2 | WP-4.2 | provenance/traceability کامل: pointer pattern (بدون کپی مقدار ورودی)؛ زنجیرهٔ derivation → formula+version → input refs → normalization/field_seq → extraction → binding WP-3.2 → Document/Page/span → Capture S1 با verified read روی هر لینک در یک trace؛ evidence-bearing-ness fail-closed (بدون binding سالم → refusal) | trace walk test + structural pointer tests | گزارش تست chain کامل + refusal بدون binding | T-4.2.2, T-4.2.3 | Traceability Walk | test_deriv_trace.py (۸ تست: chain کامل، تکرارپذیری بدون side-effect، ستون‌های pointer بدون value، عدم کپی 1080 به لایهٔ بالا) + test_deriv_service.py::test_unbound_extraction_is_refused_fail_closed + run_smoke_derivation.py (گام ۴ و ۶) | PASS | TM acceptance via WP-4.2-IMPL / 2026-10-06 |
| AC-4.2.3 | WP-4.2 | persistence طبق الگوی پروژه: SQLite فایل مجزا synchronous=FULL؛ commit اتمیک record+input refs (صفر residue)؛ INV-D-1:1 (normalization_id, formula_id, formula_version) با replay صریح؛ UNIQUE backstop؛ بدون UPDATE/DELETE؛ VOR با fingerprint sha256-v1؛ restart-safe؛ tamper → fail صریح بدون تحویل محتوا | durability/restart tests + tamper matrix + storage-gate tests | گزارش تست restart/atomicity/gates | T-4.2.2, T-4.2.3 | Durable Store + VOR | test_deriv_durability.py (۸ تست: restart/replay، zero-residue، UNIQUE backstop، بدون update/delete، gateهای UNRESOLVED/EXTRACTED/input_count=0 → IntegrityError) + test_deriv_read_path.py (۱۱ تست: tamper value/input/fp/algo، row-deletion، refused) + run_smoke_derivation.py (گام ۵–۷) | PASS | TM acceptance via WP-4.2-IMPL / 2026-10-06 |
| AC-4.2.4 | WP-4.2 | مرز: DERIVED تنها label تولیدی (storage-gated؛ UNRESOLVED هرگز ساخته/نسبت/حل نمی‌شود — P5)؛ NOT_DERIVABLE/mechanism-DEFERRED با reason code صریح و بدون persist (DEFERRED ≠ UNRESOLVED)؛ بدون unit_amount عمومی/semantic؛ بدون cross-document؛ بدون اجرای کد دلخواه (بدون eval/exec/literal در فرمول؛ import allowlist)؛ مستقل از موتور؛ رفتار Frozen P1–P4.1 دست‌نخورده | boundary tests + engine-equivalence test + full regression | گزارش تست sweep/gates + stub equivalence + رگرسیون کامل | T-4.2.1..T-4.2.4 | Boundary Enforcement | test_deriv_boundary.py (۱۵ تست: sweep بدون UNRESOLVED، quantity+total → هیچ unit_amount، cross-doc refusal، AST scan کد/float، صفر «Engine» symbol، probe لایه‌های Frozen بعد از ترافیک derivation) + test_deriv_service.py::test_identical_inputs_derive_identically_from_any_engine + رگرسیون زنده: pytest همهٔ ۵ لایه → 393/393 PASSED (292 Frozen سبز + 101 جدید) | PASS | TM acceptance via WP-4.2-IMPL / 2026-10-06 |

```text
WP-4.2 Acceptance Status: 4/4 closed — WP-4.2: IMPLEMENTED (2026-10-06، dispatch اجرایی PO/TM)
Note (2026-10-06, WP-4.2-IMPL) — ACCEPTANCE EVIDENCE (WP-4.2):
- Scope (SPEC-WP42-DER v1.0-MVP، تبدیل Scope مصوب rescoped به قرارداد): مکانیزم deterministic
  تولید DERIVED از NORMALIZED — evidence-bound، formula اعلانی versioned fingerprinted،
  arithmetic دقیق (بدون float/rounding)، provenance کامل تا Capture S1، persistence append-only
  با VOR. هیچ semantic inference/business interpretation.
- اجرای واقعی با کد: DerivationFormulaRegistry اعلانی (validation fail-closed؛ کلید
  (formula_id, version)؛ coexistence نسخه‌ها) + موتور exact-arithmetic (Fraction گویا از
  decimal string کانونی؛ DIV فقط terminating؛ خروجی minimal exact expansion) +
  DerivationStore (SQLite مجزا، synchronous=FULL، اتمیک، INV-D-1:1، CHECK DERIVED-only، بدون
  UPDATE/DELETE) + DerivationService (VOR normalization به‌عنوان تنها مسیر مقدار + binding
  WP-3.2 fail-closed + singleton resolution + output-present gate + trace walk کامل).
- جمع‌بندی شواهد: P4.2 = 101/101 PASSED + رگرسیون کامل = 393/393 PASSED (Python 3.12.14 /
  pytest 9.0.2) + SMOKE OK × ۷ (شامل run_smoke_derivation.py — ۸ گام) + اثبات AST
  (صفر float literal/call، صفر eval/exec/__import__، import allowlist، صفر symbol موتور).
- مرز اعلامی: بدون line grouping/association (تست عدد مبهم → input-ambiguous → ارجاع صریح به
  Canonicalization Gate در detail) | بدون unit_amount عمومی (registry بدون آن؛ رفتار sweep) |
  بدون cross-document (رفتاری + gate سطح store) | UNRESOLVED تولید نمی‌شود (gate سطح storage
  + sweep) | هیچ تغییر فایل Frozen P1–P4.1 (فقط additive) | هیچ تست موجودی حذف/تضعیف نشد.
- واژگان (تفکیک دقیق — SPEC §5): DERIVED = label D-01 روی خروجی derivation ذخیرشونده |
  NOT_DERIVABLE / mechanism-DEFERRED = refusal گذرای لایهٔ derivation با reason code
  (input-missing | input-ambiguous | output-present | non-exact-result) — بدون مقدار، بدون
  persist | DEFERRED لایهٔ P4.1 = status فیلد normalization | UNRESOLVED = P5 — در P4.2
  ساختاراً غیرممکن.
- Gate فاز P4 بسته نشده است (تصمیم PM+QA/PO). WP-4.2 در انتظار Acceptance رسمی PO است.
```

## WP-5.1 — R1/R2 Validation Engine

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-5.1.1 | WP-5.1 | موتور R1 اعلانی/versioned/fingerprinted (presence + exact-consistency) روی ورودی‌های verified با outcomeهای صریح VALID/INVALID/DEFERRED و حفظ provenance ورودی‌ها (pointer) — بدون اختراع مقدار | اجرای تست رفتاری + AST structural | گزارش تست + خروجی validate | T-5.1.2, T-5.1.3 | Validation Engine (src/validation) | kandoo/src/validation/tests/test_val_service.py (TestR1Presence/TestR1ExactConsistency) + test_val_rules.py (fingerprint/version) + test_val_boundary.py (no-value columns) | PASS | TM (T-5.1.4) / 2026-10-07 |
| AC-5.1.2 | WP-5.1 | موتور R2 + rounding پارامتریک D-08: tolerance/precision/mode تزریقی/versioned (بدون مقدار ثابت)؛ rounding صریح، deterministic، float-free، قابل audit و بازتولید؛ مقدار دقیق بدون rounding حفظ می‌شود؛ هیچ implicit rounding وجود ندارد | رفتار + AST (صفر float) + reproducibility | audit record در ValidationRecord + تست‌های rounding | T-5.1.2, T-5.1.3 | R2 Engine + rounding.py | test_val_rounding.py (۲۴) + test_val_service.py (TestR2*) + AST test_val_boundary.py::TestNoFloatAndNoArbitraryCode | PASS | TM (T-5.1.4) / 2026-10-07 |
| AC-5.1.3 | WP-5.1 | Persistence طبق الگوی پروژه: SQLite مجزا، synchronous=FULL، commit اتمیک، INV-V-1:1 با replay صریح، بدون UPDATE/DELETE، VOR با sha256-v1، restart-safe، tamper → شکست صریح بدون تحویل محتوا؛ gate واژگان (VALID/INVALID/DEFERRED — UNRESOLVED ساختاراً غیرممکن) | durability/tamper/gate tests | نتیجه pytest + raw SQL gates | T-5.1.2, T-5.1.3 | ValidationStore | test_val_read_path.py + test_val_durability.py + test_val_boundary.py::TestNoUnresolvedEver | PASS | TM (T-5.1.4) / 2026-10-07 |
| AC-5.1.4 | WP-5.1 | مرز و یکپارچگی: provenance chain کامل ماشین‌چک‌پذیر تا Capture S1 (شامل ورودی‌های DERIVED از طریق sub-chain WP-4.2)؛ بدون Canonicalization behavior؛ بدون business-semantic inference؛ بدون UNRESOLVED؛ engine independence؛ Frozen P1–P4.2 دست‌نخورده (رگرسیون کامل سبز) | trace tests + boundary tests + full regression | خروجی trace + git diff + pytest | T-5.1.3, T-5.1.4 | trace_validation + boundary suite | test_val_trace.py + test_val_boundary.py + test_val_e2e.py؛ رگرسیون 565/565 | PASS | TM (T-5.1.4) / 2026-10-07 |

```text
WP-5.1 Acceptance Status: 4/4 closed — WP-5.1: IMPLEMENTED (2026-10-07) | Gate فاز P5 بسته نشده است (تصمیم PM+QA/PO). WP-5.1 در انتظار Acceptance رسمی PO است.

Note (2026-10-07, T-5.1.4) — ACCEPTANCE EVIDENCE (WP-5.1):
- شواهد اجرای زندهٔ رسمی همین روز: P5.1 = 172/172 PASSED؛ رگرسیون کامل = 565/565 PASSED
  (54 capture + 72 reconstruction + 74 extraction [38+36 binding] + 92 normalization +
  101 derivation + 172 validation؛ Python 3.12.14 / pytest 9.0.2)؛ SMOKE OK × ۸
  (شامل run_smoke_validation.py — ۸ گام؛ مسیر سرد با پایگاه دادهٔ تازه).
- اثبات واژگان (SPEC §5): outcome ذخیره‌شونده فقط VALID | INVALID | DEFERRED —
  sweep سطح SQL + CHECK gate؛ UNRESOLVED تولید/ذخیره نمی‌شود (D-01: P5 domain layer)؛
  DEFERRED ≠ UNRESOLVED در detail/reason تست شد؛ هیچ invoice state (REVIEW/REJECT)
  تولید یا ذخیره نمی‌شود — WP-5.2 (AS-03/AD-04). mapping INVALID/DEFERRED → REVIEW
  فقط یادداشت downstream است (D-08) و در این WP پیاده نشده.
- اثبات rounding (D-08): هیچ مقدار ثابتی hardcode نشده (پارامترها REQUIRED و
  constructor-injected، بخشی از fingerprint)؛ تفاوت واقعی HALF_UP/HALF_EVEN روی tie
  دقیق (666.65/2 = 333.325) رفتار-تست شد؛ audit record (rule_id/rule_version/precision/
  mode/input/output) داخل ValidationRecord ثبت و بازتولید آن رفتار-تست شد؛ ورودی
  non-terminating به‌صورت "p/q" کانونی ثبت می‌شود (بدون truncate).
- مرز اعلامی: بدون Canonicalization (بدون mapping/grouping/matching/identity — تست‌های
  رفتاری + AST + ستون‌های value در schema وجود ندارند) | بدون cross-document (scope =
  یک normalization record + derivationهای آن) | بدون ایجاد value (فقط verdict + audit) |
  provenance P4.2 از طریق sub-chain مصرف می‌شود، نه دور زده.
- Frozen Layer Protection: تغییر کد فقط additive (src/validation/ + smoke + spec)؛
  git diff پ1–P4.2 = صفر؛ هیچ تست موجودی حذف/تضعیف نشد.
- Known pre-existing flake (خارج از WP-5.1): extraction/tests/test_binding_durability.py::
  test_concurrent_bind_appends_are_exact (Frozen P3) تحت stress لوپ ~۱۰٪ flake (race
  برنامه‌ریزی thread)؛ در اجرای رسمی نهایی PASS؛ تغییر سطح صفر در P3؛ reopen نشد —
  برای توجه PM/QA ثبت می‌شود.
```

## WP-5.2 — Validation State Machine + REVIEW Queue

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-5.2.1 | WP-5.2 | State Machine deterministic با واژگان عیناً Frozen (VALID \| INVALID \| DEFERRED \| UNRESOLVED + REVIEW/REJECT طبق AD-04)؛ هر transition صریح/deterministic/auditable/testable با priority اعلانی T1..T5؛ هیچ state اضافه/تغییرنام‌شده | تست mapping کامل (هر route) + vocabulary sweep + CHECK gates | خروجی pytest + state/disposition/reason در DomainStateRecord | T-5.2.2, T-5.2.3 | State Machine (src/validation_domain/machine.py) | test_vsm_state.py (۲۲: هر ۵ route + اولویت + twin صادقانه) + test_vsm_boundary.py::TestFrozenVocabularySweep + CHECK-gate tamper refusals در test_vsm_read_path.py | PASS | TM (T-5.2.4) / 2026-10-07 |
| AC-5.2.2 | WP-5.2 | ایجاد UNRESOLVED فقط field-level و فقط طبق D-01 order و معنای Frozen؛ reason/status مشخص؛ provenance حفظ‌شده؛ قابل trace؛ ambiguous ≠ UNRESOLVED؛ هیچ auto-resolve | تست رفتاری + sweep | FieldProjectionRow با d01-no-valid-method + trace تا Capture S1 | T-5.2.2, T-5.2.3 | UNRESOLVED creation (machine.py::project_fields) | test_vsm_unresolved.py (۸) + test_vsm_boundary.py::TestNoSemanticResolution | PASS | TM (T-5.2.4) / 2026-10-07 |
| AC-5.2.3 | WP-5.2 | REVIEW Queue واقعی: durable، deterministic، idempotent (INV-R-1:1)، duplicate کنترل‌شده، reason/provenance-carrying، Verify-on-Read، lifecycle append-only hash-chained با CLOSE terminal و status مشتق — بدون UPDATE/DELETE و بدون semantic resolver | durability/tamper/lifecycle tests + AST (صفر UPDATE/DELETE) | ReviewQueueItem + ReviewQueueEvent + خروجی pytest | T-5.2.2, T-5.2.3 | REVIEW Queue (store.py + service.py) | test_vsm_review.py (۱۳) + test_vsm_durability.py (۱۳) + test_vsm_read_path.py::TestReviewTamperMatrix + AST TestAppendOnlyHistory | PASS | TM (T-5.2.4) / 2026-10-07 |
| AC-5.2.4 | WP-5.2 | مرز و یکپارچگی: provenance chain کامل ماشین‌چک‌پذیر تا Capture S1 (از طریق sub-walkهای کل-زنجیرهٔ WP-5.1)؛ بدون Canonicalization behavior؛ بدون semantic resolution؛ بدون product/customer matching؛ بدون Canonical Invoice creation؛ یکپارچگی واقعی با P5.1؛ Frozen P1–P5.1 دست‌نخورده (رگرسیون کامل سبز) | trace tests + boundary tests + full regression | خروجی trace + git diff + pytest | T-5.2.3, T-5.2.4 | trace_domain_state + boundary suite | test_vsm_trace.py + test_vsm_boundary.py + test_vsm_e2e.py؛ رگرسیون 690/690 | PASS | TM (T-5.2.4) / 2026-10-07 |

```text
WP-5.2 Acceptance Status: 4/4 closed — WP-5.2: IMPLEMENTED (2026-10-07) | Gate فاز P5 بسته نشده است (تصمیم PM+QA/PO). WP-5.2 در انتظار Acceptance رسمی PO است.

Note (2026-10-07, T-5.2.4) — ACCEPTANCE EVIDENCE (WP-5.2):
- شواهد اجرای زندهٔ رسمی همین روز: P5.2 = 125/125 PASSED؛ رگرسیون کامل = 690/690
  PASSED (54 capture + 72 reconstruction + 74 extraction [38+36 binding] + 92
  normalization + 101 derivation + 172 validation + 125 validation_domain؛
  Python 3.12.14 / pytest 9.0.2)؛ SMOKE OK × ۹ (۸ قبلی + run_smoke_validation_domain.py
  — ۸ گام؛ مسیر سرد با پایگاه دادهٔ تازه).
- اثبات واژگان (SPEC §3): domain_state ذخیره‌شونده فقط VALID | INVALID | DEFERRED |
  UNRESOLVED (عیناً dispatch) و disposition فقط CLEAR | REVIEW | REJECT (AD-04) —
  sweep سطح SQL + CHECK gates (state↔disposition consistency؛ حتی tamper مستقیم SQL
  توسط CHECK رد می‌شود — رفتار-تست شد)؛ هیچ state اضافه/تغییرنام/ترکیب.
- اثبات mapping (SPEC §3/OD-S8): T1 decisive (absent/present-not-usable/mismatch) →
  REJECT؛ T2 (mismatch-beyond-tolerance/mismatch-after-rounding) → REVIEW طبق D-08؛
  T3 field-UNRESOLVED → REVIEW طبق D-01/AD-04؛ T4 rule-DEFERRED → REVIEW؛ T5 →
  VALID/CLEAR؛ اولویت ثابت با تست mixed-outcome (decisive > tolerance > unresolved >
  deferred)؛ twin probe صادقانه (همان rule با expression سازگار → VALID — state
  machine هرگز rubber-stamp نمی‌کند).
- اثبات UNRESOLVED (D-01): فقط field-level با reason ثابت d01-no-valid-method؛
  origin/pointer relay حفظ می‌شود (NORMALIZED → field_seq؛ DERIVED → derivation_id)؛
  present-but-not-normalized (P4.1 DEFERRED status) → UNRESOLVED با relay وضعیت
  upstream؛ ambiguous (≥2 candidate) هرگز UNRESOLVED نمی‌شود — candidate_count ثبت و
  association به Canonicalization Gate ارجاع می‌شود (معنای D-01 verbatim حفظ شد)؛
  هیچ auto-resolve در read/trace/replay.
- اثبات REVIEW queue (SPEC §5): INV-R-1:1 (یک item per state record — UNIQUE
  backstop)؛ replay صریح (DomainStateAlreadyExists)؛ reasons فقط از کدهای route؛
  lifecycle append-only با hash-chain (prev_event_fingerprint) — tamper/deletion
  chain را می‌شکند و خواندن محتوا را قطع می‌کند؛ CLOSE terminal (partial UNIQUE + in-
  txn check — حتی بعد از restart)؛ status همیشه از history مشتق می‌شود؛ AST: صفر
  UPDATE/DELETE در کل لایه.
- مرز اعلامی: بدون Canonicalization/matching/grouping/identity (رفتاری + AST + sweep
  symbolهای ممنوع) | بدون اجرای validation/derivation/normalization (spy-test: صفر
  فراخوانی upstream در projection) | بدون تغییر byte-level در DBهای upstream (hash
  قبل/بعد) | بدون invoice-like column در schema | completeness gate: missing و extra
  records هر دو رد می‌شوند.
- Frozen Layer Protection: تغییر کد فقط additive (src/validation_domain/ + smoke +
  spec + registers/README)؛ git diff P1–P5.1 = صفر؛ هیچ تست موجودی حذف/تضعیف نشد.
- Known pre-existing flake (خارج از WP-5.2، طبق dispatch دست‌نخورده):
  extraction/tests/test_binding_durability.py::test_concurrent_bind_appends_are_exact
  (Frozen P3) — در اجرای رسمی نهایی این WP PASS شد؛ فقط برای توجه PM/QA ثبت می‌شود.
```

---

## WP-6.1 — Canonicalization Gate

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-6.1.1 | WP-6.1 | Gate deterministic، declared-priority، fail-closed: routing verified P5.2 states به paths عیناً dispatch §14 (ACCEPTED \| REJECTED \| REVIEW \| ALREADY_CANONICALIZED)؛ هر تصمیم صریح/auditable/testable؛ VALID/CLEAR لازم اما کافی نیست؛ هیچ state/decision خارج واژگان | decision-table tests + vocabulary sweep + CHECK gates + tamper-before-replay test | خروجی pytest + GateDecisionRecord در store | T-6.1.2, T-6.1.3 | Gate decision engine (src/canonicalization/gate.py + service.py) | test_cg_decision.py (۱۷) + test_cg_boundary.py::TestFrozenVocabularySweep + CHECK-gate refusals | PASS | TM (T-6.1.4) / 2026-10-07 |
| AC-6.1.2 | WP-6.1 | Identity resolution دقیقاً D-02/D-03: فقط مسیر deterministic S2 (triad کاملاً استخراج+تأییدشده)، CAPTURE_SCOPED صریح، incomplete/conflicting/undetermined → REVIEW، multiple candidates هرگز auto-resolve نمی‌شوند، فقط exact matching، adapter path RESERVED نه اختراع | identity tests + AST symbol sweep + value-honesty probe | IdentityResolution + identity_fingerprint + pointer rows | T-6.1.2, T-6.1.3 | Identity resolution (src/canonicalization/identity.py) | test_cg_identity.py (۱۸) + test_cg_boundary.py AST probes | PASS | TM (T-6.1.4) / 2026-10-07 |
| AC-6.1.3 | WP-6.1 | Canonical Invoice admission: فقط داخل تراکنش Gate، فقط از verified inputs، source-independent (D-04)، origin عیناً frozen enum، deterministic fingerprint، immutable (بدون UPDATE/DELETE)، idempotent (S1 replay + S2 duplicate rejection — INV-CI-1:1) | invoice tests + direct-SQL UNIQUE backstop tests + atomicity zero-residue + restart | CanonicalInvoiceRecord + pointers + خروجی pytest | T-6.1.2, T-6.1.3 | Admission store (src/canonicalization/store.py) | test_cg_invoice.py (۱۵) + test_cg_idempotency.py (۹) | PASS | TM (T-6.1.4) / 2026-10-07 |
| AC-6.1.4 | WP-6.1 | مرز و یکپارچگی: provenance chain کامل ماشین‌چک‌پذیر تا Capture S1 (trace_domain_state مصرف می‌شود نه bypass)؛ بدون downstream mutation (Inventory/Sale/KPI/Customer)؛ بدون اجرای upstream (spy-proven)؛ بدون fuzzy/matching/AI؛ Frozen P1–P5.2 دست‌نخورده (رگرسیون کامل سبز) | trace tests + boundary tests + spy tests + full regression + git diff | خروجی trace + pytest + git diff صفر | T-6.1.3, T-6.1.4 | trace_canonical_invoice + boundary suite | test_cg_provenance.py (۱۰) + test_cg_boundary.py (۳۴) + test_cg_service.py (۹)؛ رگرسیون 802/802 | PASS | TM (T-6.1.4) / 2026-10-07 |

```text
WP-6.1 Acceptance Status: 4/4 closed — WP-6.1: IMPLEMENTED (2026-10-07) | Gate فاز P6 بسته نشده است (WP-6.2 در صف dispatch). WP-6.1 در انتظار Acceptance رسمی PO است.

Note (2026-10-07, T-6.1.4) — ACCEPTANCE EVIDENCE (WP-6.1):
- شواهد اجرای زندهٔ رسمی همین روز: P6.1 = 112/112 PASSED؛ رگرسیون کامل = 802/802
  PASSED (54 capture + 72 reconstruction + 74 extraction + 92 normalization + 101
  derivation + 172 validation + 125 validation_domain + 112 canonicalization؛
  Python 3.12.14 / pytest 9.0.2)؛ SMOKE OK × ۱۰ (همه ۹ قبلی +
  run_smoke_canonicalization.py — ۸ گام؛ مسیر سرد با پایگاه دادهٔ تازه).
- اثبات واژگان (SPEC §4/§6): decision ذخیره‌شونده فقط ACCEPTED | REJECTED | REVIEW |
  ALREADY_CANONICALIZED (عیناً dispatch §14) و origin فقط KANDOO_SALE |
  HOLOO_CAPTURE | OTHER_POS_CAPTURE (عیناً dispatch §7؛ KANDOO_SALE روی ورودی
  P5.2-sourced refuse می‌شود — OD-G6/G7 — چون native flow (AS-02) بدون capture
  pipeline است) — sweep سطح SQL + CHECK gates؛ هیچ decision/origin اضافه.
- اثبات decision table (SPEC §4/OD-G1): G0 replay (INV-D-1:1، قبل از routing،
  بعد از verification fail-closed)؛ G1 decisive-INVALID → REJECTED (AD-04/OD-S9)؛
  G2 REVIEW-disposition → REVIEW با relay عیناً state_reason P5.2 (d08-mismatch/
  d01-unresolved/validation-deferred — CL-1 بدون پارافریز) و ارجاع upstream_review_id
  بدون duplicate آیتم (OD-G9)؛ G3 CAPTURE_SCOPED → REVIEW (incomplete/conflicting/
  undetermined — D-03 ناقص/متعارض/ambiguity)؛ G4 replay سطح capture با S1 →
  ALREADY_CANONICALIZED (D-02)؛ G5 S2 کامل+دقیق از capture متفاوت → REJECTED
  d03-definite-document-duplicate (قطعی)؛ G6 → ACCEPTED. ترتیب ثابت با تست‌های
  priority (G1/G2 قبل از identity؛ G4 قبل از G5).
- اثبات identity (D-02/D-03 — SPEC §5): فقط مسیر deterministic دوم D-02 — triad
  شماره فاکتور+تاریخ+جمع «کاملاً استخراج و تأیید شده» (دقیقاً یک NORMALIZED قابل
  استفاده per role در read تأییدشدهٔ WP-4.1 + state VALID/CLEAR)؛ otherwise صراحتاً
  CAPTURE_SCOPED؛ adapter-document-id path RESERVED اعلان شد (OD-G5 — بدون producer
  در pipeline فعلی؛ D-04 post-freeze) — هیچ اختراعی. multiple candidates → REVIEW و
  هرگز auto-resolve (dispatch §6)؛ empty value قابل استفاده نیست (OD-G2)؛
  identity_fingerprint = sha256-v1(origin + سه مقدار canonical) — مقایسه فقط
  exact-equality (fingerprint یکسان برای S2 یکسان؛ متفاوت با origin متفاوت —
  scope منبع)؛ صفر fuzzy/heuristic/similarity/AI (AST symbol sweep + import
  allowlist + رفتار).
- اثبات admission (SPEC §6/§8): فقط در تراکنش G6 با INV-CI-1:1؛ source-independent
  (بدون ستون source-schema؛ tuple فقط به‌صورت fingerprint + ۳ pointer row)؛
  immutable (AST صفر UPDATE/DELETE؛ tamper مستقیم SQL → IntegrityFailure)؛
  deterministic fingerprint (recompute = stored)؛ backstopهای UNIQUE (capture_s1،
  identity_fingerprint، decision_id، single-CLOSE) حتی در برابر INSERT مستقیم SQL؛
  atomicity: شکست اجباری mid-commit → zero residue (همهٔ جدول‌ها خالی)؛ restart:
  reopen + re-verify + status مشتق + idempotent replay.
- اثبات provenance (SPEC §9): trace_canonical_invoice → decision → trace_domain_state
  (کل-زنجیرهٔ P5.2 شامل sub-walks WP-5.1 با لینک «DERIVED via derivation … WP-4.2
  whole-chain re-verified» و tail capture: OK) → re-join سه pointer روی read
  تأییدشده؛ broken link در هر لایه upstream (normalization/binding/vsm) →
  CanonicalizationInputIntegrityFailure با zero residue — هیچ admission؛ tamper
  بعد از admission → trace می‌شکند (re-verify در هر walk).
- مرز اعلامی (dispatch §11): بدون Inventory/Sale/KPI/Customer mutation؛ بدون
  product/customer matching (هویت این WP = DOCUMENT identity طبق D-02/D-03)؛ بدون
  tax/currency/accounting؛ بدون AI identity resolution؛ بدون OCR؛ بدون اجرای
  upstream (spy-test: validate/normalize/derive/project هرگز فراخوانی نمی‌شوند)؛
  بدون Canonical Assembly/issuance رسمی (WP-6.2)؛ row-count stability لایه‌های
  Frozen در برابر ترافیک gate (write-on-read خودِ لایه‌ها مثل F-08 مستثنا و مستند).
- Frozen Layer Protection: تغییر کد فقط additive (src/canonicalization/ + smoke +
  spec + registers/README)؛ git diff P1–P5.2 = صفر؛ هیچ تست موجودی حذف/تضعیف نشد.
- Known pre-existing flake (خارج از WP-6.1، طبق dispatch دست‌نخورده):
  extraction/tests/test_binding_durability.py::test_concurrent_bind_appends_are_exact
  (Frozen P3) — در اجرای رسمی نهایی این WP PASS شد (5/5 تکرار مستقل)؛ فقط برای
  توجه PM/QA ثبت می‌شود.
```

## WP-6.2 — Canonical Assembly + invoice_id Issuance

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-6.2.1 | WP-6.2 | مرز P6.1: فقط admission عیناً ACCEPTED از طریق verified read + whole-chain trace مصرف می‌شود (هرگز bypass)؛ برای REVIEW/REJECTED/ALREADY_CANONICALIZED هیچ invoice ساخته نمی‌شود؛ بدون تصمیم مجدد canonicalization؛ بدون اجرای upstream (spy-proven) | service tests + spy tests + refusal tests + row-count stability + full regression | AssemblyCompleted فقط برای ACCEPTED؛ Refused/IntegrityFailure بقیه؛ git diff صفر | T-6.2.2, T-6.2.3 | CanonicalAssemblyService (src/canonical_assembly/service.py) | test_ca_service.py (۱۷) + test_ca_boundary.py + رگرسیون 902/902 | PASS | TM (T-6.2.4) / 2026-10-08 |
| AC-6.2.2 | WP-6.2 | Assembly دقیق: canonical fields byte-identical با verified reads (بدون rename/ invention/default — AS-04)؛ provenance D-01 عیناً EXTRACTED \| DERIVED؛ header anchors = سه نقش D-02 با re-join + کنسistency انکر (A6)؛ خطوط فقط DECLARED (بدون کشف)؛ ترتیب deterministic؛ absent/empty/ambiguous طبق OD-A5؛ customer ref صراحتاً ABSENT (D-06)؛ بدون حسابگری بین fieldها (OD-A7) | engine tests + byte-identity probes + ambiguity refusal + empty-line rejection + anchor mismatch fail-closed | CanonicalFieldEntry/LineField/Anchor رکوردها + خروجی pytest | T-6.2.2, T-6.2.3 | Pure assembly engine (src/canonical_assembly/assembly.py) | test_ca_assembly.py (۲۵) + test_ca_lines.py (۹) + test_ca_service.py بخش‌های مربوط | PASS | TM (T-6.2.4) / 2026-10-08 |
| AC-6.2.3 | WP-6.2 | invoice_id = هویت Kandoo-issued admission، VERBATIM (بدون UUID/فرمول جدید — AST-proven صفر uuid/random)؛ unique/stable/collision-safe؛ idempotent replay (همان declaration → AlreadyAssembled؛ declaration متفاوت → refusal — OD-A8)؛ duplicate canonicalization fail-closed؛ commit اتمیک invoice+anchors+fields+lines (zero residue) | issuance tests + replay/drift tests + direct-SQL UNIQUE backstops + forced mid-commit failure + repeated issuance | IssuedCanonicalInvoiceRecord + خروجی pytest | T-6.2.2, T-6.2.3 | issuance + store (src/canonical_assembly/store.py) | test_ca_invoice.py (۲۰) + test_ca_durability.py (۷) | PASS | TM (T-6.2.4) / 2026-10-08 |
| AC-6.2.4 | WP-6.2 | Persistence الگوی پروژه (SQLite FULL، اتمیک، immutable/VOR/sha256-v1، CHECK/UNIQUE، restart-safe، tamper-evident، بدون UPDATE/DELETE — AST) + provenance کامل ماشین‌چک‌پذیر تا Capture S1 با re-join هر field/line؛ Frozen P1–P6.1 دست‌نخورده (رگرسیون کامل سبز) | durability/tamper/AST tests + trace tests + full regression + git diff | خروجی trace + pytest + git diff صفر | T-6.2.3, T-6.2.4 | store + trace + boundary suite | test_ca_provenance.py (۹) + test_ca_durability.py + test_ca_boundary.py (۱۳)؛ رگرسیون 902/902 | PASS | TM (T-6.2.4) / 2026-10-08 |

```text
WP-6.2 Acceptance Status: 4/4 closed — WP-6.2: IMPLEMENTED (2026-10-08) | Gate فاز P6 بسته نشده است (Acceptance رسمی PO pending). WP-6.2 در انتظار Acceptance رسمی PO است.

Note (2026-10-08, T-6.2.4) — ACCEPTANCE EVIDENCE (WP-6.2):
- شواهد اجرای زندهٔ رسمی همین روز: P6.2 = 100/100 PASSED؛ رگرسیون کامل = 902/902
  PASSED (54 capture + 72 reconstruction + 74 extraction + 92 normalization + 101
  derivation + 172 validation + 125 validation_domain + 112 canonicalization + 100
  canonical_assembly؛ Python 3.12.14 / pytest 9.0.2)؛ SMOKE OK × ۱۱ (همه ۱۰ قبلی +
  run_smoke_canonical_assembly.py — ۶ گام: ACCEPTED→assembly+trace → REVIEW→
  هیچ invoice → replay+declaration-drift → restart → tamper → survival sweep؛
  مسیر سرد با پایگاه دادهٔ تازه).
- اثبات مرز (dispatch §4 — SPEC §4): تنها ورودی مجاز = admission رکورد تصمیم
  ACCEPTED از P6.1 (read_canonical_invoice — VOR) + trace_canonical_invoice
  (consumed، هرگز bypass — spy: هر دو فراخوانی در هر assemble دیده می‌شوند)؛
  REVIEW/REJECTED/ALREADY_CANONICALIZED هیچ admission ندارند و هر تلاش assemble →
  AssemblyRequestRefused (no-p6.1-accepted-admission) با zero residue؛ هیچ متد
  canonicalize/admit/route روی سطح عمومی سرویس نیست (structural test)؛
  project_domain_state/validate/normalize/derive/extract/reconstruct هرگز فراخوانی
  نمی‌شوند (spy-test)؛ row-count stability لایه‌های Frozen در برابر assemble.
- اثبات assembly (dispatch §5/§6 — SPEC §5/§6): inventory = هر NORMALIZED قابل
  استفاده (field_seq order) + هر DERIVED تأییدشدهٔ P4.2 (deterministic order)؛
  مقادیر byte-identical با verified reads (behavioral probe روی هر field/line)؛
  field_name عیناً engine vocabulary (بدون rename)؛ provenance عیناً D-01
  (EXTRACTED | DERIVED — sweep SQL)؛ UNRESOLVED هرگز ساخته نمی‌شود؛ header anchors
  = سه نقش D-02 از pointerهای admission با A6 (quote دقیق serialization OD-G4؛
  mismatch → IntegrityFailure)؛ خطوط فقط DECLARED (line_key → سه نقش → field)؛
  ≥2 ردیف → refusal declared-field-ambiguous (هرگز auto-resolution)؛ 0 ردیف →
  ABSENT صریح؛ خط خالی → empty-line-rejected صریح و هرگز ذخیره نمی‌شود؛ ترتیب
  خطوط = sort صریح (استقلال از dict-order — دو اعلان هم‌ارز با ترتیب dict متفاوت
  محتوای یکسان)؛ بدون حسابگری بین fieldها (totals semantics در P5.1)؛ customer
  reference = NULL + deferred-wp9.1-d06-no-deterministic-link (D-06/OD-A9).
- اثبات issuance (dispatch §7/§8 — SPEC §7): invoice_id == canonical_invoice_id
  admission (verbatim — OD-A1؛ D-02 هویت سوم؛ OD-G8 handover)؛ AST: صفر
  uuid/random/secrets در کل لایه (هیچ identifier mint نمی‌شود)؛ unique (PK +
  UNIQUE(admission_decision_id) + UNIQUE(identity_fingerprint) — INSERT مستقیم SQL
  → IntegrityError)؛ replay همان declaration → AssemblyAlreadyAssembled (رکورد
  موجود verbatim، بدون ردیف جدید — ۵ بار تکرار: دقیقاً یک Completed)؛ همان
  admission با declaration متفاوت → refusal assembly-declaration-conflict (هیچ
  invoice دوم و هیچ reshape خاموش)؛ declaration_fingerprint = sha256-v1
  serialization key-sorted (استقلال از ترتیب dict).
- اثبات persistence (SPEC §8): فایل مجزا canonical-assembly.db؛ synchronous=FULL؛
  commit اتمیک invoice+anchors+fields+lines+line_fields — شکست اجباری
  fingerprint mid-commit → همهٔ ۵ جدول صفر ردیف (zero residue) و admission بعدش
  قابل استفاده؛ restart: reopen + VOR کامل + trace سبز + replay idempotent؛ tamper
  مستقیم SQL روی invoice/field/line/anchor → AssemblyReadIntegrityFailure (محتوا
  withhold می‌شود)؛ DELETE ردیف → inconsistent-set VerificationUnavailable؛ CHECK
  gates (origin خارج واژگان، provenance↔pointer، value↔absent) → IntegrityError؛
  AST: صفر UPDATE/DELETE/DROP در کل لایه.
- اثبات provenance (SPEC §9): trace_assembled_invoice در یک فراخوانی: issued
  invoice (VOR کامل محتوا) → admission + trace_canonical_invoice (کل-زنجیره تا
  Capture S1 — consumed) → re-join هر EXTRACTED/DERIVED field و هر line field با
  byte-identity؛ tamper normalization/binding upstream → AssemblyInputIntegrityFailure
  با zero residue؛ tamper بعد از issuance → trace می‌شکند.
- اثبات ساختاری (dispatch §25/§26): AST صفر UPDATE/DELETE/DROP؛ صفر import
  uuid/random/secrets/eval/exec/subprocess/socket؛ صفر float literal؛ import
  allowlist (stdlib مجاز محدود + لایه‌های پروژه)؛ صفر identifier ممنوع
  (fuzzy/similarity/levenshtein/ocr/semantic/inventory/kpi/auto_create/...)؛ صفر
  ارجاع مستقیم به جدول‌های storeهای upstream؛ واژگان verbatim (سweep constants).
- Frozen Layer Protection: تغییر کد فقط additive (src/canonical_assembly/ + smoke +
  spec + registers/README)؛ git diff P1–P6.1 = صفر؛ هیچ تست موجودی حذف/تضعیف نشد؛
  flake ثبت‌شدهٔ P3 در اجرای رسمی این WP PASS شد (طبق dispatch دست‌نخورده).
```

## WP-7.1 — Identity Resolution (S1 / S2 / CAPTURE_SCOPED)

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-7.1.1 | WP-7.1 | تفکیک صریح و deterministic حالت‌های S1/S2/CAPTURE_SCOPED: S2 فقط با triad فروزن «کاملاً استخراج و تأیید شده» از طریق primitive فروزن P6.1 مصرف‌شده VERBATIM (بدون فرمول جدید/fork — AST بدون hashlib)؛ CAPTURE_SCOPED صریح با reason پایدار (state غیر VALID بدون هیچ مصرف مقداری)؛ ابهام ≥2 هرگز auto-select و هرگز UNRESOLVED (D-01)؛ هیچ مقداری ابداع نمی‌شود | resolver/service tests + AST reuse proof + vocabulary sweep + spy (بدون read_normalization برای non-VALID) | IdentityResolutionRecorded با scope/reason/evidence + خروجی pytest | T-7.1.2, T-7.1.3 | IdentityResolutionService + resolver (src/identity_resolution/) | test_ir_resolution.py (۲۸) + test_ir_boundary.py بخش reuse/واژگان + test_ir_service.py | PASS | TM (T-7.1.4) / 2026-10-08 |
| AC-7.1.2 | WP-7.1 | Idempotency/duplicate طبق dispatch §11 دقیقاً: Case A replay S1 (یک هویت، یک resolution دائمی، صفر duplicate — حتی بین stateهای مختلف و پس از restart؛ verified-not-blind)؛ Case B same S2/captureهای متفاوت → definite duplicate + دقیقاً یک هویت سند + observation ارجاع به original؛ Case C/F تفاوت → هویت متفاوت بدون duplicate؛ Case D incomplete → CAPTURE_SCOPED؛ Case E ابهام → بدون انتخاب خودکار؛ drift replay → refusal؛ concurrency: race ۸ thread + backstop UNIQUE → دقیقاً یک resolution | idempotency/service tests + restart + threaded race + direct-SQL UNIQUE backstop | IdentityReplay/IdentityDefiniteDuplicate + observation row + خروجی pytest | T-7.1.2, T-7.1.3 | replay/duplicate mechanics (service.py + store.py) | test_ir_idempotency.py (۱۹) + test_ir_service.py (۱۲) + test_ir_durability.py بخش backstopها | PASS | TM (T-7.1.4) / 2026-10-08 |
| AC-7.1.3 | WP-7.1 | Persistence الگوی پروژه (SQLite FULL، commit اتمیک resolution+roles+observation، immutable/VOR/sha256-v1، CHECK/UNIQUE gates، restart-safe، tamper-evident، بدون UPDATE/DELETE — AST) + INV-IR-S1:1 (یک resolution per capture_s1) + INV-IR-DUP:1؛ شکست اجباری mid-commit → zero residue؛ forged row و hash-consistent forged row → محتوا withhold می‌شود | durability/tamper tests + forced failure + direct-SQL INSERT/CHECK probes + AST | خروجی pytest + row-count zero بعد از شکست | T-7.1.2, T-7.1.3 | IdentityResolutionStore (src/identity_resolution/store.py) | test_ir_durability.py (۲۴) + test_ir_boundary.py AST | PASS | TM (T-7.1.4) / 2026-10-08 |
| AC-7.1.4 | WP-7.1 | Provenance کامل ماشین‌چک‌پذیر تا Capture S1 (V2 trace_domain_state consumed-never-bypassed — spy-proven؛ broken/tampered provenance حتی برای replay → FAIL CLOSED با zero residue؛ pointer discipline — هیچ مقدار raw در store؛ re-join byte-identity)؛ Frozen P1–P6.2 byte-untouched (رگرسیون کامل 1010/1010 سبز)؛ بدون fuzzy/heuristic/AI (identifier sweep)؛ بدون اجرای upstream | provenance tests + spy + tamper upstream + full regression + git diff | خروجی trace/read + pytest + git diff صفر | T-7.1.2, T-7.1.3, T-7.1.4 | service ladder + provenance (src/identity_resolution/service.py) | test_ir_provenance.py (۱۱) + test_ir_boundary.py spy/stability + رگرسیون 1010/1010 | PASS | TM (T-7.1.4) / 2026-10-08 |

```text
WP-7.1 Acceptance Status: 4/4 closed — WP-7.1: IMPLEMENTED (2026-10-08) | Gate فاز P7 بسته نشده است (Acceptance رسمی PO pending). WP-7.1 در انتظار Acceptance رسمی PO است.

Note (2026-10-08, T-7.1.4) — ACCEPTANCE EVIDENCE (WP-7.1):
- شواهد اجرای زندهٔ رسمی همین روز: P7.1 = 108/108 PASSED (+3 تکرار مستقل
  108/108 — بی‌flake)؛ رگرسیون کامل = 1010/1010 PASSED (54 capture + 72
  reconstruction + 74 extraction + 92 normalization + 101 derivation + 172
  validation + 125 validation_domain + 112 canonicalization + 100
  canonical_assembly + 108 identity_resolution؛ Python 3.12.14 / pytest
  9.0.2)؛ SMOKE OK × ۱۲ (همه ۱۱ قبلی + run_smoke_identity_resolution.py —
  ۸ گام: S2 recorded+verified read → S1 replay (همان state + re-projection →
  verbatim، یک resolution) → definite duplicate (twin → observation، یک
  fingerprint) → CAPTURE_SCOPED (ابهام حفظ‌شده / incomplete) → drift refusal
  → restart → forged-row withheld → survival sweep؛ مسیر سرد با پایگاه دادهٔ
  تازه).
- اثبات حالت‌ها (dispatch §7 — SPEC §5): هر resolution هر سه هویت D-02 را
  صریح حمل می‌کند — S1 = capture_s1 (UNIQUE؛ از verified staterecord پس از
  whole-chain walk)؛ S2 = فقط triad کامل+تأییدشده از primitive فروزن P6.1
  (resolve_identity/validate_binding import — بدون فرمول دوم؛ AST: بدون
  hashlib در کل لایه) با سه ردیف evidence (candidate_count=1 +
  resolved_field_seq) قابل re-join byte-identity از read تأییدشده WP-4.1؛
  CAPTURE_SCOPED = fingerprint خالی + reason پایدار (سه کد D-03 عیناً از
  P6.1 + s2-not-attempted-state-not-valid)؛ برای state غیر VALID/CLEAR هیچ
  read_normalization حتی فراخوانی نمی‌شود (spy: صفر فراخوانی) — resolver
  هرگز مقدار unverified نمی‌بیند.
- اثبات idempotency/duplicate (dispatch §11/§13 — SPEC §4/§6): Case A —
  resolve مکرر همان state → دقیقاً یک ردیف، Replay verbatim (record + rows +
  observation)؛ replay بین stateهای مختلف همان capture (re-projection با
  ruleset جدید → state_id متفاوت، capture_s1 یکسان) → Replay؛ پس از restart →
  Replay؛ ردیف دستکاری‌شده → IntegrityFailure (replay کور هرگز)؛ Case B —
  twin/third-order (بایت متفاوت، مقدار یکسان) → IdentityDefiniteDuplicate با
  observation append-only ارجاع به original (deterministic earliest
  created_at/resolution_id) و دقیقاً یک fingerprint متمایز در DB؛ Case C/F —
  تفاوت یک کاراکتر → fingerprint متفاوت، بدون observation؛ Case D/E —
  incomplete/conflicting → CAPTURE_SCOPED با candidate evidence حفظ‌شده
  (counts + field_seqs صعودی، resolved NULL)؛ drift replay (origin یا binding
  متفاوت) → replay-declaration-drift refusal با zero residue؛ سپس درخواست
  اصلی دوباره Replay می‌دهد. concurrency — race ۸ thread با storeهای
  thread-local و ورودی verified ثابت: دقیقاً 1 Recorded + 7 Replay + یک ردیف
  (BEGIN IMMEDIATE + چک in-transaction + UNIQUE(capture_s1))؛ store-level
  race: یک برنده، ۷ ResolutionDuplicate به existing_id برنده؛ race
  چند-capture با یک هویت: هر دو observation به original واحد.
- اثبات persistence (SPEC §7/§8): فایل مجزا identity-resolution.db؛
  synchronous=FULL؛ commit اتمیک resolution+role rows+observation — شکست
  اجباری capability در fingerprint observation (بعد از insert) → همهٔ ۳ جدول
  بدون ردیف جدید (zero residue) و retry تمیز موفق؛ restart: reopen + VOR +
  replay سبز؛ ماتریس tamper: دستکاری capture_id / record_fingerprint /
  source_field_name / original_capture_s1 → IdentityReadIntegrityFailure
  (محتوا withhold)؛ forged row با hash غلط → IntegrityFailure؛ forged row با
  hash درست ولی بدون role rows → structural gate → VerificationUnavailable؛
  CHECK gates حتی tamper مستقیم scope_reason/candidate_count را رد می‌کنند
  (IntegrityError)؛ UNIQUE backstops با INSERT مستقیم SQL رد می‌شوند؛ AST:
  صفر UPDATE/DELETE/DROP در کل لایه؛ uuid فقط bookkeeping (service.py، فقط
  resolution_id/observation_id) — هویت همیشه fingerprint deterministic است
  (دو stack مستقل + corpus یکسان → fingerprint یکسان، bookkeeping متفاوت).
- اثبات provenance (SPEC §9): spy — trace_domain_state در هر resolve دقیقاً
  یک‌بار؛ انکرهای رکورد == verified state record؛ tamper
  normalization_records/domain_state_records → IdentityInputIntegrityFailure
  با zero residue؛ دستکاری upstream بعد از resolution حتی replay را می‌شکند
  (V1/V2 قبل از R0)؛ sweep SQL: هیچ مقدار raw (شماره/تاریخ/جمع) در هیچ جدول
  identity نیست — فقط pointerها و counts؛ re-join role rows روی read
  تأییدشده byte-identical است.
- مرز اعلامی (dispatch §14): بدون Product/Customer matching؛ بدون
  OCR/AI/heuristic/fuzzy (identifier sweep AST)؛ بدون
  Inventory/Sales/Digital Invoice/Holoo/Sync/UI؛ بدون mint/ارجاع invoice_id
  (بدون ستون invoice؛ سطح عمومی سرویس فقط resolve/read_resolution/
  read_resolution_by_capture)؛ spy: هیچ validate/normalize/derive/project/
  extract/reconstruct/ingest در resolve فراخوانی نمی‌شود؛ row-count
  stability لایه‌های Frozen در برابر resolve + replay.
- Frozen Layer Protection: تغییر کد فقط additive (src/identity_resolution/ +
  smoke + spec + registers/README)؛ git diff P1–P6.2 = صفر؛ هیچ تست موجودی
  حذف/تضعیف نشد؛ flake ثبت‌شدهٔ P3 در اجرای رسمی این WP PASS شد (طبق dispatch
  دست‌نخورده). نکتهٔ صادقانهٔ مستند: race همزمان روی stack کامل، رفتار
  concurrent خود لایه‌های Frozen (P5.1) را نمایان می‌کند — خارج از مرز این
  WP؛ تست concurrency این WP عمداً لایه هویت را با ورودی verified ثابت race
  می‌کند و رفتار Frozen دست‌نخورده ماند.
```

---

## WP-7.2 — Reprint & Duplicate Flows

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-7.2.1 | WP-7.2 | Reprint flow قطعی: ارائهٔ مجدد همان capture → `FlowReprintRecognized` verbatim — دقیقاً یک resolution دائمی، یک disposition دائمی، صفر ردیف جدید (row-count stability لایه‌ها)؛ حتی با state_id متفاوت روی همان capture_s1 و پس از restart؛ drift declaration در reprint → refusal عیناً relay (replay-declaration-drift) با zero residue؛ tampered disposition → fail-closed (هرگز از ردیف دستکاری‌شده شناخته نمی‌شود) | reprint/durability tests + restart + direct-SQL tamper + row-count stability | FlowReprintRecognized verbatim + خروجی pytest | T-7.2.2, T-7.2.3 | FlowReprintRecognized + zero-row discipline (src/duplicate_flows/service.py) | test_df_reprint.py (۱۱) + test_df_durability.py بخش tamper | PASS | TM (T-7.2.4) / 2026-10-08 |
| AC-7.2.2 | WP-7.2 | Duplicate flow طبق D-03 فقط exact: twin/third-order captureهای متفاوت با همان S2 دقیق → `FlowDuplicateRecognized` ارجاع به original قطعی (OD-IR-E) + observation؛ همیشه دقیقاً یک هویت سند؛ register دائمی (`duplicates_of`) کامل و منسجم؛ Case F تفاوت یک-کاراکتری → هرگز duplicate؛ مرز whitespace طبق قرارداد فروزن؛ CAPTURE_SCOPED هرگز duplicate و هرگز حدس زده نمی‌شود (D-03: فقط dedup سطح capture تضمین است)؛ ابهام (Case E) حفظ و هرگز auto-select نمی‌شود | duplicate/duplicate-boundary tests + register assertions + exact-only sweeps | FlowDuplicateRecognized + duplicates_of + خروجی pytest | T-7.2.2, T-7.2.3 | duplicate mechanics + register (service.py + store.py) | test_df_duplicate.py (۱۰) + test_df_reprint.py بخش third-capture | PASS | TM (T-7.2.4) / 2026-10-08 |
| AC-7.2.3 | WP-7.2 | Delegation + persistence: WP-7.1 resolve مصرف VERBATIM (spy-proven؛ بدون فرمول هویت، بدون hashlib، بدون import canonicalization — AST)؛ الگوی store پروژه کامل (SQLite FULL، commit اتمیک تک‌ردیفی، immutable، VOR، sha256-v1 از طریق سرویس S1، CHECK/UNIQUE gates، tamper detection، restart-safe، بدون UPDATE/DELETE — AST، zero residue در شکست اجباری)؛ INV-DF-1:1 با backstop UNIQUE اثبات‌شده در race ۸-thread (برنده یک، بازندگان read-only) | service/durability tests + spy + AST + forced failure + threaded race | خروجی pytest + یک disposition در race | T-7.2.2, T-7.2.3 | DuplicateFlowService + FlowDispositionStore (src/duplicate_flows/) | test_df_service.py (۱۳) + test_df_durability.py (۹) + test_df_boundary.py AST/race | PASS | TM (T-7.2.4) / 2026-10-08 |
| AC-7.2.4 | WP-7.2 | مرزها و یکپارچگی: باز-تأیید همهٔ identity facts لینک‌شده در هر read جریان (resolution/original/observation از طریق readهای تأییدشده WP-7.1 — هرگز pointer کور)؛ structural gates بین-store‌ای (drift هر انکر → withhold)؛ Frozen P1–P7.1 byte-untouched (رگرسیون کامل سبز؛ git diff صفر روی فایل‌های tracked)؛ بدون واژگان/انگهی canonicalization (ACCEPTED/REJECTED/REVIEW/ALREADY_CANONICALIZED هرگز تصمیم/حاشیه‌نویسی نمی‌شوند)، بدون invoice_id، بدون عملیات REVIEW، بدون fuzzy/heuristic/AI؛ F5 backfill قطعی و مستقل از ترتیب استقرار (OD-DF-E) | linked-verification tests + forged/hash-consistent tamper matrix + AST + vocabulary sweeps + full regression + git diff | خروجی read + pytest + git diff صفر | T-7.2.2, T-7.2.3, T-7.2.4 | verified reads + structural gates + boundary proofs | test_df_boundary.py (۱۵) + test_df_durability.py بخش linked-tamper + رگرسیون کامل | PASS | TM (T-7.2.4) / 2026-10-08 |

```text
WP-7.2 Acceptance Status: 4/4 closed — WP-7.2: IMPLEMENTED (2026-10-08) | Gate فاز P7 بسته نشده است (Acceptance رسمی PO pending). WP-7.2 در انتظار Acceptance رسمی PO است.

Note (2026-10-08, T-7.2.4) — ACCEPTANCE EVIDENCE (WP-7.2):
- شواهد اجرای زندهٔ رسمی همین روز: P7.2 = 58/58 PASSED (+2 تکرار مستقل
  58/58)؛ رگرسیون کامل = 1067/1068 جمع‌کل (1067 PASSED + 1 flake ثبت‌شدهٔ
  از پیش موجود)؛ اجرای خالص بدون flake = 1067/1067 PASSED (54 capture + 72
  reconstruction + 74 extraction + 92 normalization + 101 derivation + 172
  validation + 125 validation_domain + 112 canonicalization + 100
  canonical_assembly + 108 identity_resolution + 58 duplicate_flows؛
  Python 3.12.14 / pytest 9.0.2)؛ SMOKE OK × ۱۳ (همه ۱۲ قبلی +
  run_smoke_duplicate_flows.py — ۸ گام: establish → reprint verbatim
  صفر-ردیف → definite duplicate + register → CAPTURE_SCOPED → drift
  refusal → restart → tamper withhold → survival/vocabulary sweep؛ مسیر
  سرد با پایگاه دادهٔ تازه).
- Flake ثبت‌شدهٔ از پیش موجود (نه ناشی از WP-7.2):
  identity_resolution/tests/test_ir_provenance.py::
  test_no_raw_pipeline_values_are_stored — وابسته به تاریخ اجرا: وقتی
  تاریخ UTC روزِ اجرا با تاریخ invoice در corpus (2026-10-08) برابر شود،
  timestamp کتاب‌نگاری created_at خود رکورد (متادیتای مشروع هر لایه) با
  مقدار تاریخ corpus برخورد کرده و false-positive می‌سازد؛ تنها hit در
  اجرای بازتولید، ستون created_at بود ⇒ pointer discipline سالم است و هیچ
  مقدار pipeline ذخیره نشده است؛ در worktree خالص HEAD 9d7f372 (بدون کد
  WP-7.2) نیز بازتولید شد؛ در اجرای رسمی WP-7.1 (UTC 2026-10-07) همین تست
  PASS بود. طبق حکمرانی Frozen، فایل تست دست‌نخورده ماند (الگوی flake-note
  ثبت‌شدهٔ WP-6.1/WP-7.1) و اصلاح آن به dispatch بعدی TM/PO موکول است.
```

---

## WP-8.1 — Product Exact Match

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-8.1.1 | WP-8.1 | Catalog register: ثبت explicit/idempotent — تکرار همان (kind,value) → CatalogIdentityReplay verbatim با صفر ردیف جدید؛ UNIQUE(kind,value) به‌عنوان backstop قطعیت (اثبات با SQL مستقیم)؛ API ثبت فاقد هر پارامتر capture/invoice ⇒ جهش کاتالوگ از مسیر capture ساختاراً ناممکن (D-06/DEF3 analog — OD-PM2/PM3)؛ ذخیرهٔ verbatim بدون trim/fold/normalization | test_pm_catalog.py + signature/AST probes + direct-SQL probes | CatalogIdentityRegistered/Replay + خروجی pytest | T-8.1.2, T-8.1.3 | Catalog register (src/product_candidate/store.py + service.py) | test_pm_catalog.py (۱۰) | PASS | TM (T-8.1.4) / 2026-10-08 |
| AC-8.1.2 | WP-8.1 | Exact match دقیقاً طبق D-05: مرجع declared با قاعدهٔ exactly-one روی inventory فاکتور P6.2 (0/≥2 → refusal — هرگز auto-resolution)؛ byte-exact روی (kind,value) → EXACT_MATCHED ارجاع به catalog identity؛ 0 → UNRESOLVED دائمی(no-catalog-identity)؛ ≥2 → fail-closed integrity؛ replay verbatim صفر-ردیف و هرگز re-decide؛ هر دو provenance D-01 معتبر؛ بدون fuzzy/semantic/AI/confidence/approval/candidate — AST identifier sweep | test_pm_match.py + AST vocabulary sweep | ProductExactMatched + ProductReferenceUnresolved + replay + خروجی pytest | T-8.1.2, T-8.1.3 | matching ladder M1–M6 (service.py) | test_pm_match.py (۱۲) + test_pm_boundary.py sweep | PASS | TM (T-8.1.4) / 2026-10-08 |
| AC-8.1.3 | WP-8.1 | Delegation + persistence: read verified P6.2 مصرف VERBATIM (spy-proven دقیقاً یک read در مسیر عادی؛ fail-closed passthrough)؛ INV-PM-1:1 با UNIQUE backstop اثبات‌شده در race ۸-thread (یک برنده + ۷ replay read-only)؛ الگوی store پروژه کامل (SQLite FULL، commit اتمیک تک‌ردیفی، immutable، VOR، sha256-v1 از طریق S1، CHECK+UNIQUE، restart-safe، بدون UPDATE/DELETE/hashlib — AST)؛ determinism استقرار | test_pm_service.py + test_pm_durability.py + spy + AST + forced failure + threaded race | خروجی pytest + یک match در race | T-8.1.2, T-8.1.3 | ProductCandidateService + ProductCandidateStore | test_pm_service.py (۸) + test_pm_durability.py (۱۲) | PASS | TM (T-8.1.4) / 2026-10-08 |
| AC-8.1.4 | WP-8.1 | مرزها و یکپارچگی: pointer discipline (هیچ ستون/ردیف value — schema probe + AST)؛ read تأییدشده = VOR خود + باز-تأیید فاکتور P6.2 لینک‌شده + re-join اشاره‌گر + باز-تأیید کاتالوگ + اثبات زندهٔ byte-identity؛ tamper matrix کامل withhold (own row / flip شکل / hash-consistent forged → structural gates / فاکتور لینک‌شده / کاتالوگ / مقدار canonical)؛ row-count stability لایه‌های Frozen؛ Frozen P1–P7.2 byte-untouched (رگرسیون کامل + git diff) | linked-verification tests + tamper matrix + schema/AST probes + full regression + git diff | خروجی read + pytest + git diff صفر | T-8.1.2, T-8.1.3, T-8.1.4 | verified reads + structural gates + boundary proofs | test_pm_boundary.py (۱۵) + test_pm_durability.py + رگرسیون کامل | PASS | TM (T-8.1.4) / 2026-10-08 |

```text
WP-8.1 Acceptance Status: 4/4 closed — WP-8.1: IMPLEMENTED (2026-10-08) | Gate فاز P8 بسته نشده است (Acceptance رسمی PO pending). WP-8.1 در انتظار Acceptance رسمی PO است.

Note (2026-10-08, T-8.1.4) — ACCEPTANCE EVIDENCE (WP-8.1):
- شواهد اجرای زندهٔ رسمی همین روز: P8.1 = 57/57 PASSED (+2 تکرار مستقل 57/57)؛
  رگرسیون کامل = 1125 جمع‌کل (1124 PASSED + 1 flake ثبت‌شدهٔ از پیش موجود)؛
  SMOKE OK = run_smoke_product_matching.py (۸ گام: register → byte-exact
  EXACT_MATCHED + اثبات زندهٔ byte-identity → replay verbatim صفر-ردیف →
  UNRESOLVED دائمی که ثبت بعدی بازنویسی‌اش نمی‌کند → refusals با zero residue
  → restart → tamper withhold → byte-identity case-diff → survival/vocabulary
  sweep؛ مسیر سرد با پایگاه دادهٔ تازه).
- Flake ثبت‌شدهٔ از پیش موجود (نه ناشی از WP-8.1): همان flake تاریخ‌حساس
  suite فروزن WP-7.1 (test_ir_provenance.py::test_no_raw_pipeline_values_
  are_stored) — در dispatch قبلی در worktree خالص HEAD 9d7f372 بدون کد
  WP-7.2 بازتولید شده؛ طبق Flake Policy فایل Frozen دست‌نخورده ماند و
  تفکیک آن از شکست‌های جدید طبق عرف پروژه انجام شد (تنها FAILED همین
  مورد بود؛ صفر شکست جدید).
- Boundary declaration: WP-8.2 (Candidate Generation & Approval) در این
  Mission اجرا نشد — نیازمند تصمیم Product Owner برای policy تولید کاندید
  (فازی/occurrence-based طبق D-05 delegated) و ماتریس عملیاتی approval
  (DEF2)؛ طبق Mission dispatch «Do not invent fuzzy matching rules» هیچ
  چنین سطحی ساخته نشد و ابهام ابهام ماند.
```

---

## WP-9.1 — Deterministic Customer Linking

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-9.1.1 | WP-9.1 | Customer register: ثبت explicit/idempotent فقط برای مشتریان **موجود** — تکرار همان (kind,value) → CustomerIdentityReplay verbatim با صفر ردیف جدید؛ UNIQUE(kind,value) به‌عنوان backstop قطعیت (اثبات با SQL مستقیم)؛ API ثبت فاقد هر پارامتر capture/invoice (D-06/DEF3 — OD-CL2/CL3)؛ ذخیرهٔ verbatim بدون trim/fold/normalization | test_cl_customers.py + signature/AST probes + direct-SQL probes | CustomerIdentityRegistered/Replay + خروجی pytest | T-9.1.2, T-9.1.3 | Customer register (src/customer_linking/store.py + service.py) | test_cl_customers.py (۱۰) | PASS | TM (T-9.1.4) / 2026-10-08 |
| AC-9.1.2 | WP-9.1 | Deterministic link دقیقاً طبق قاعدهٔ برقرار: مرجع declared با قاعدهٔ exactly-one روی inventory فاکتور P6.2 (0/≥2 → refusal — هرگز auto-resolution)؛ byte-exact روی (kind,value) → LINKED به مشتری موجود؛ 0 → UNRESOLVED دائمی(no-customer-identity) و **هیچ مشتری‌ای ساخته نمی‌شود** (اثبات ساختاری: صفر INSERT در service؛ دو INSERT مجزا در store؛ هر outcome رجیستر را رشد نمی‌دهد)؛ ≥2 → fail-closed integrity؛ replay verbatim صفر-ردیف و هرگز re-decide (حتی پس از ثبت بعدی)؛ بدون fuzzy/AI/best-match/merge/enrichment — AST identifier sweep | test_cl_link.py + no-creation probes + AST sweep | CustomerLinked + CustomerLinkUnresolved + replay + خروجی pytest | T-9.1.2, T-9.1.3 | linking ladder L1–L6 (service.py) | test_cl_link.py (۱۱) + test_cl_boundary.py probes | PASS | TM (T-9.1.4) / 2026-10-08 |
| AC-9.1.3 | WP-9.1 | Delegation + persistence: read verified P6.2 مصرف VERBATIM (spy-proven دقیقاً یک read در مسیر عادی؛ fail-closed passthrough)؛ INV-CL-1:1 با UNIQUE backstop اثبات‌شده در race ۸-thread (یک برنده + ۷ replay read-only)؛ الگوی store پروژه کامل (SQLite FULL، commit اتمیک تک‌ردیفی، immutable، VOR، sha256-v1 از طریق S1، CHECK+UNIQUE، restart-safe، بدون UPDATE/DELETE/hashlib — AST)؛ determinism استقرار | test_cl_service.py + test_cl_durability.py + spy + AST + forced failure + threaded race | خروجی pytest + یک link در race | T-9.1.2, T-9.1.3 | CustomerLinkingService + CustomerLinkingStore | test_cl_service.py (۸) + test_cl_durability.py (۱۲) | PASS | TM (T-9.1.4) / 2026-10-08 |
| AC-9.1.4 | WP-9.1 | مرزها و یکپارچگی: pointer discipline (هیچ ستون/ردیف value — schema probe + AST)؛ read تأییدشده = VOR خود + باز-تأیید فاکتور P6.2 لینک‌شده + re-join اشاره‌گر + باز-تأیید مشتری + اثبات زندهٔ byte-identity؛ tamper matrix کامل withhold؛ OD-A9 فاکتور فروزن دست‌خورده باقی می‌ماند (خروجی = رجیستر additive)؛ row-count stability لایه‌های Frozen؛ Frozen P1–P8.1 byte-untouched (رگرسیون کامل + git diff) | linked-verification tests + tamper matrix + schema/AST probes + full regression + git diff | خروجی read + pytest + git diff صفر | T-9.1.2, T-9.1.3, T-9.1.4 | verified reads + structural gates + boundary proofs | test_cl_boundary.py (۱۸) + test_cl_durability.py + رگرسیون کامل | PASS | TM (T-9.1.4) / 2026-10-08 |

```text
WP-9.1 Acceptance Status: 4/4 closed — WP-9.1: IMPLEMENTED (2026-10-08) | Gate فاز P9 بسته نشده است (Acceptance رسمی PO pending). WP-9.1 در انتظار Acceptance رسمی PO است.

Note (2026-10-08, T-9.1.4) — ACCEPTANCE EVIDENCE (WP-9.1):
- شواهد اجرای زندهٔ رسمی همین روز: P9.1 = 59/59 PASSED (+2 تکرار مستقل 59/59)؛
  رگرسیون کامل = 1184 جمع‌کل (1183 PASSED + 1 flake ثبت‌شدهٔ از پیش موجود)؛
  SMOKE OK = run_smoke_customer_linking.py (۸ گام: register → byte-exact
  LINKED + اثبات زندهٔ byte-identity → replay verbatim صفر-ردیف →
  customer-looking data بدون مشتری موجود → UNRESOLVED دائمی با رجیستر EMPTY
  (no auto-create — D-06/DEF3) و بازنویسی‌نشدن با ثبت بعدی → refusals با
  zero residue → restart → tamper withhold → byte-identity → survival/
  vocabulary sweep؛ مسیر سرد با پایگاه دادهٔ تازه).
- Flake ثبت‌شدهٔ از پیش موجود (نه ناشی از WP-9.1): همان flake تاریخ‌حساس
  suite فروزن WP-7.1 (test_ir_provenance.py::test_no_raw_pipeline_values_
  are_stored) — طبق Flake Policy فایل Frozen دست‌نخورده ماند و تفکیک آن از
  شکست‌های جدید طبق عرف پروژه انجام شد (تنها FAILED همین مورد بود؛ صفر
  شکست جدید).
- Boundary declaration: قاعدهٔ link = تنها semantics deterministic برقرار
  پروژه (D-05/P6.1 exact definitive-identifier)؛ هیچ سیاست فازی/آستانه/
  merge/dedup/enrichment پیاده‌سازی نشد (D-06/DEF3 — تصمیم PO؛ WP-11.x
  enrichment خارج از Freeze).
```

## WP-10.1 — Digital Invoice Lifecycle (Phase P10)

| AC ID | WP | Requirement | Verification Method | Expected Evidence | Linked Task(s) | Deliverable | Evidence Location | Status | Accepted By / Date |
|---|---|---|---|---|---|---|---|---|---|
| AC-10.1.1 | WP-10.1 | Entry & boundary: Digital Invoice فقط برای Canonical Invoice صادرشدهٔ P6.2 باز می‌شود — از طریق read تأییدشده + whole-chain trace (spy-proven, never bypassed, صفر اجرای upstream)؛ INV-DI-1:1 با UNIQUE backstop اثبات‌شده در race ۸-thread (یک برنده + ۷ replay read-only)؛ invoice ناشناخته → refused؛ upstream دستکاری‌شده/زنجیرهٔ شکسته → fail-closed با zero residue؛ origin عیناً از رکورد تأییدشده (CHECK واژگان فروزن)؛ بدون هر semantics ممنوع: ساخت Sale، مشتری، product، REVIEW، ارائه، inventory (AST + vocabulary sweep) | test_di_open.py + spy + AST + 8-thread race + full regression | DigitalInvoiceOpened/OpenReplay + خروجی pytest | T-10.1.2, T-10.1.3 | open ladder O1–O4 (service.py) | test_di_open.py (۱۰) + test_di_durability.py (race) | PASS | TM (T-10.1.4) / 2026-10-08 |
| AC-10.1.2 | WP-10.1 | State machine: واژگان فروزن DRAFT \| EXTRACTED \| VALIDATED \| ISSUED \| REVOKED \| SUPERSEDED عیناً منتقل شده (بدون افزودن/تغییر نام/مترادف — sweep ساختاری)؛ ماتریس انتقال دقیقاً §5.2 (DB CHECK + mirror پایتون + تست‌های رفتاری: transitions قانونی پیش می‌روند؛ skip/backward/terminal-exit با zero residue رد می‌شوند)؛ REVOKE/SUPERSEDE از ISSUED منحصراً و متقابلاً منحصر؛ چرخهٔ supersede ساختاراً ناممکن؛ هیچ رفتار خودکار — هر event پیامد یک act صریح تأییدشده است | test_di_lifecycle.py + CHECK probes via direct SQL + AST sweep | LifecycleAdvanced/Replay/Refused + خروجی pytest | T-10.1.2, T-10.1.3 | ماتریس §5.2 در model/store/service | test_di_lifecycle.py (۱۵) + test_di_durability.py CHECK probes | PASS | TM (T-10.1.4) / 2026-10-08 |
| AC-10.1.3 | WP-10.1 | Idempotency & auditability: replay verbatim با صفر ردیف جدید در همهٔ stateهای هدف (open + هر act — D-03)؛ supersede replay نیازمند byte-match replacement (تضاد → refusal؛ OD-DI-H)؛ event chain append-only با seq gap-free به‌صورت CAS درون-تراکنشی (append با state کهنه ساختاراً ناممکن — اثبات در race ۸-thread advance که همهٔ بازنده‌ها replay شدند)؛ projection = pure function زنجیره (determinism cross-stack)؛ هر ردیف sha256-v1 از طریق سرویس S1؛ REVOKE-vs-SUPERSEDE race → دقیقاً یک terminal act، بازنده refusal صادقانه | test_di_lifecycle.py + test_di_durability.py (races + determinism) | LifecycleReplay verbatim + row-count stability + خروجی pytest | T-10.1.2, T-10.1.3 | CAS append + projection pure (store.py/model.py) | test_di_lifecycle.py (۱۵) + test_di_durability.py (races) | PASS | TM (T-10.1.4) / 2026-10-08 |
| AC-10.1.4 | WP-10.1 | Persistence & provenance: الگوی کامل store پروژه (SQLite FULL، commit اتمیک، immutable بدون UPDATE/DELETE — AST، VOR، CHECK/UNIQUE gates، restart-safe، tamper-evident، zero residue در forced failure)؛ read ladder = own VOR + یکپارچگی زنجیرهٔ event + باز-تأیید زندهٔ P6.2 + cross-check anchor + باز-تأیید یک-سطحی replacement؛ trace_digital_invoice به‌صورت machine-checkable یک head link روی زنجیرهٔ سالم P6.2 تا Capture S1؛ pointer discipline (هیچ مقدار canonical ذخیره نمی‌شود — schema probe)؛ Frozen P1–P9 byte-untouched (رگرسیون کامل + git diff) | test_di_service.py + test_di_durability.py + tamper matrix + restart + full regression + git diff | خروجی read/trace + pytest + git diff صفر | T-10.1.2, T-10.1.3, T-10.1.4 | verified reads + trace + structural gates | test_di_service.py (۱۴) + test_di_durability.py (۱۵) + رگرسیون کامل | PASS | TM (T-10.1.4) / 2026-10-08 |

```text
WP-10.1 Acceptance Status: 4/4 closed — WP-10.1: IMPLEMENTED (2026-10-08) | Gate فاز P10 بسته نشده است (Acceptance رسمی PO pending). WP-10.1 در انتظار Acceptance رسمی PO است.

Note (2026-10-08, T-10.1.4) — ACCEPTANCE EVIDENCE (WP-10.1):
- شواهد اجرای زندهٔ رسمی همین روز: P10.1 = 54/54 PASSED (+2 تکرار مستقل
  54/54)؛ رگرسیون کامل = 1238 جمع‌کل (1237 PASSED + 1 flake ثبت‌شدهٔ از پیش
  موجود)؛ SMOKE OK = run_smoke_digital_invoice.py (شانزدهمین smoke — ۸ گام
  cold-start: open→DRAFT، پیشروی صریح→ISSUED، replay صفر-ردیف، refusals با
  zero residue، supersede با replacement تأییدشده + byte-match conflict،
  revoke، restart survival، tamper withhold + vocabulary sweep).
- Flake ثبت‌شدهٔ از پیش موجود (نه ناشی از WP-10.1): همان flake تاریخ‌حساس
  suite فروزن WP-7.1 (test_ir_provenance.py::test_no_raw_pipeline_values_
  are_stored) — طبق Flake Policy فایل Frozen دست‌نخورده ماند و تفکیک آن از
  شکست‌های جدید طبق عرف پروژه انجام شد (تنها FAILED همین مورد بود؛ صفر
  شکست جدید).
- Boundary declaration: واژگان lifecycle عیناً از Mission dispatch فروزن
  منتقل شد (AS-03)؛ ماتریس انتقال/act semantics = delegated details
  اعلام‌شده (OD-DI-A..K)؛ هیچ state جدید، هیچ رفتار خودکار، هیچ مسیر
  native-Sale، هیچ semantics مشتری/product/REVIEW/ارائه پیاده‌سازی نشد
  (WP-10.2 Delivery = DEFERRED — DEF5/PO + بدون تعریف کامل WP).
```

---

## P11 — WP-11.1 (Holoo DB Spike — READ-ONLY) — Mission «HOLOO INTEGRATION — READ-ONLY SPIKE» (2026-10-08)

| AC ID | WP | پذیرش (Acceptance Criterion) | Evidence Type | Output Artifact | Tasks | محل تعریف | Tests | نتیجه | تصویب |
|---|---|---|---|---|---|---|---|---|---|
| AC-11.1.1 | WP-11.1 | Read path provenance-preserving: باز شدن منبع Holoo-shaped فقط با mode=ro + query_only=ON (read-back=1 ثبت در گزارش)؛ discovery کامل و sorted با PRAGMAهای read-whitelisted؛ extraction فقط با نگاشت DECLARED (بدون حدس schema — D-04/§2.7)؛ مقادیر verbatim با encoding type-tagged (unicode/NULL/int64-max/REAL-hex/BLOB-base64/identifier فاصله‌دار)؛ تکرار ×2 و ×5 byte-identical؛ audit SQL verbatim execution-true | test_hs_read_path.py + test_hs_durability.py + خروجی pytest | HolooSpikeReport (to_json_bytes قطعی) | T-11.1.2, T-11.1.3 | SPEC §7/§8/§9/§10 | test_hs_read_path.py (۱۰) + determinism tests | PASS | TM (T-11.1.4) / 2026-10-08 |
| AC-11.1.2 | WP-11.1 | Zero-mutation اثبات‌شده در پنج لایه: L1 engine (INSERT/UPDATE/DELETE/CREATE/DROP از طریق connection تولیدی → OperationalError)؛ L2 query_only=ON با read-back؛ L3 گارد (۲۴ class mutating/malformed → ReadOnlyViolation پیش از engine؛ audit خالی)؛ L4 AST probes؛ L5 bytes (hash S1 + size + mtime + header change-counter + dir-listing قبل==بعد در ۱ و ۵ اجرا + write-refusal hammer؛ بدون side-file −wal/−shm/−journal)؛ گزارش فقط با open==close hash صادر می‌شود | test_hs_guards.py + test_hs_durability.py + smoke steps 4–6 | ReadOnlyViolation/refusal evidence + L5 fingerprints | T-11.1.2, T-11.1.3 | SPEC §6 ladder | guards (۲۱) + durability (۱۱) | PASS | TM (T-11.1.4) / 2026-10-08 |
| AC-11.1.3 | WP-11.1 | Fail-closed و صداقت: منبع missing/directory/غیر-SQLite/خالی → hard failure بدون گزارش؛ SQLite بی‌ربط → MAPPING_REFUSED با reason شامل نام جدول‌های کشف‌شده و صفر ردیف ساختگی؛ جدول/ستون/order_by ناموجود → refusal دقیق؛ بدون case-guessing؛ duplicate selection names → MappingRefused کل request؛ selectionهای سالم ادامه می‌یابند | test_hs_failures.py + smoke step 7 | refusals verbatim در mapping_validations | T-11.1.2, T-11.1.3 | SPEC §5/§11 | test_hs_failures.py (۱۲) | PASS | TM (T-11.1.4) / 2026-10-08 |
| AC-11.1.4 | WP-11.1 | Boundary discipline: خروجی فقط گزارش و فقط-حافظه (package هیچ فایلی نمی‌نویسد — JSON توسط runner نوشته شد — D-04/OD-HS-J)؛ import allowlist (stdlib + capture — بدون هر sibling دامنه‌ای)؛ fixture builder هرگز از package تولیدی import نمی‌شود (OD-HS-K sweep)؛ vocabulary sweep (۵ نقش گزارشی؛ بدون SALE/CANONICAL/REVIEW/…)؛ role نامعتبر در construction رد می‌شود؛ additive-only — Frozen P1–P10 byte-untouched (رگرسیون کامل 1316/1317 + ۱ flake ثبت‌شدهٔ از پیش موجود) | test_hs_guards.py (AST/sweep) + full regression + smoke step 8 | spike-report.json (smoke) + خروجی pytest | T-11.1.2, T-11.1.3, T-11.1.4 | SPEC §2/§3/§14 | AST + sweeps + رگرسیون کامل | PASS | TM (T-11.1.4) / 2026-10-08 |

Evidence note (P11): 79/79 dedicated tests PASSED ×2 independent repeats؛
SMOKE 17/17 (run_smoke_holoo_spike — 8-step cold-start)؛ رگرسیون کامل 1317
collected = 1316 PASSED + ۱ flake ثبت‌شدهٔ از پیش موجود (identity_resolution/
tests/test_ir_provenance.py::test_no_raw_pipeline_values_are_stored —
date-sensitive، active on UTC 2026-10-08، frozen WP-7.1 — طبق Flake Policy
تفکیک شد؛ فایل فروزن دست‌نخورده). Spike روی fixture SYNTHETIC اجرا شد؛ هیچ
سیستم واقعی Holoo لمس نشد (offline-safe؛ عملیات منبع واقعی = عملگر/PO).

---

## P12 — WP-12.1 (Corpus Assembly) — Mission «P12 PILOT — CORPUS ASSEMBLY AND DOWNSTREAM IMPLEMENTATION» (2026-10-08)

| AC ID | WP | پذیرش (Acceptance Criterion) | Evidence Type | Output Artifact | Tasks | محل تعریف | Tests | نتیجه | تصویب |
|---|---|---|---|---|---|---|---|---|---|
| AC-12.1.1 | WP-12.1 | قطعیت مونتاژ: همان (template, entry_count, seed_base) → corpus بایت-یکسان با address محتوایی (corpus_version_id = manifest fingerprint)؛ تکرار ×2 مستقل → CorpusReplay verbatim با صفر ردیف جدید (اثبات row-count)؛ هر اعلان متفاوت → address متمایز (اثبات ۴-way)؛ قطعیت بین دو store فایل مستقل | test_co_service.py + test_co_store.py + خروجی pytest | CorpusAssembled/CorpusReplay + manifest.content-address | T-12.1.2, T-12.1.3 | SPEC §5/§7 | determinism tests + replay ×4 | PASS | TM (T-12.1.4) / 2026-10-08 |
| AC-12.1.2 | WP-12.1 | برچسب‌گذاری و provenance: origin_role = SYNTHETIC_PILOT_FIXTURE و marking دقیق روی هر entry و هر manifest (service + خواندن)؛ ردِ fail-closed هر origin/marking دیگر در هر سه سطح service/CHECK/AST؛ label kinds انحصاراً VALUE/ABSENT با قیود شکل (VALUE همیشه expected_value؛ ABSENT هرگز) | test_co_boundary.py + test_co_store.py (CHECK probes) | marking contract probes | T-12.1.2, T-12.1.3 | SPEC §2.1/§3 | CHECK + AST + sweeps | PASS | TM (T-12.1.4) / 2026-10-08 |
| AC-12.1.3 | WP-12.1 | یکپارچگی و persistence: fingerprint sha256-v1 از طریق S1 (بدون hash دوم — AST)؛ VOR هر ردیف در هر خواندن با بازسازی canonical bytes از ستون‌ها؛ tamper matrix کامل withhold (فلیپ بایت/fingerprint/ordinal/count/ledger/DELETE → CorpusReadIntegrityFailure/Refused؛ هرگز تحویل جزئی)؛ restart-safe؛ UNIQUE(corpus_version_id, ordinal) + UNIQUE(entry_fingerprint) با SQL مستقیم؛ zero-residue در forced failure (proxy connection — rollback کل نسخه) | test_co_store.py + test_co_service.py + smoke step 6 | tamper withhold + replay + zero-residue evidence | T-12.1.2, T-12.1.3 | SPEC §6/§8 | tamper matrix + CHECK/UNIQUE probes | PASS | TM (T-12.1.4) / 2026-10-08 |
| AC-12.1.4 | WP-12.1 | مرزها: import allowlist (فقط stdlib + capture — AST)؛ sweep کل packageهای تولیدی: هیچ package‌ای corpus را import نمی‌کند؛ clock-free مطلق (بدون datetime/time/now/created_at — AST)؛ append-only (بدون UPDATE/DELETE/DROP/ALTER — AST + رشتهٔ SQL)؛ بدون file I/O مستقیم؛ sweep smoke runnerهای قبلی؛ vocabulary sweep (بدون Sale/Customer/Inventory/DigitalInvoice)؛ قالب‌ها از پنجرهٔ flake تاریخ-حساس دور (OD-CA-G)؛ additive-only — Frozen P1–P11.1 byte-untouched (رگرسیون کامل) | test_co_boundary.py + full regression + git diff | AST/sweep probes + git diff صفر | T-12.1.2, T-12.1.3, T-12.1.4 | SPEC §2/§11 | AST + sweeps + رگرسیون کامل | PASS | TM (T-12.1.4) / 2026-10-08 |

Evidence note (P12.1): 90/90 dedicated tests PASSED ×3 independent repeats؛
SMOKE 18/18 (run_smoke_corpus — 8-step cold-start)؛ رگرسیون کامل 1440 جمع‌کل
= 1439 PASSED + ۱ flake ثبت‌شدهٔ از پیش موجود (identity_resolution/tests/
test_ir_provenance.py::test_no_raw_pipeline_values_are_stored —
date-sensitive، active on UTC 2026-10-08، frozen WP-7.1 — طبق Flake Policy
تفکیک شد؛ فایل فروزن دست‌خورده). هیچ سیستم واقعی استفاده نشد؛ تمام مواد
SYNTHETIC و برچسب‌خورده‌اند.

---

## P12 — WP-12.2 (Calibration Runs) — همان Mission (2026-10-08)

| AC ID | WP | پذیرش (Acceptance Criterion) | Evidence Type | Output Artifact | Tasks | محل تعریف | Tests | نتیجه | تصویب |
|---|---|---|---|---|---|---|---|---|---|
| AC-12.2.1 | WP-12.2 | اجرای اندازه‌گیری: pipeline فروزن (M1..M9 تا Gate P6.1) روی هر entry در workspace ایزوله؛ مصرف verbatim سرویس‌ها (بدون بازپیاده‌سازی — OD-CR-B)؛ طبقه‌بندی فیلد MATCH/MISMATCH/MISSING/UNEXPECTED_PRESENT + تصمیم gate از vocabulary فروزن؛ گزارش قطعی — ×2/×3 workspace تازه → JSON بایت-یکسان؛ بدون uuid/ISO-timestamp/path (regex-proven)؛ echo config verbatim | test_cal_runner.py + خروجی pytest | CalibrationReport.to_json_bytes | T-12.2.2, T-12.2.3 | SPEC §4/§5/§7 | determinism + shape + echo tests | PASS | TM (T-12.2.4) / 2026-10-08 |
| AC-12.2.2 | WP-12.2 | سوییپ D-08: هر کاندید declared → sub-workspace تازه + rule declared «kandoo-cal-declared-gross-agreement» (R2 tolerated-equality، target = gross چاپ‌شده) از طریق engine فروزن؛ شمارش‌های within/beyond/not_evaluable با texture pinned (0.00 → همهٔ residuals beyond؛ 0.02 → همه within؛ 0.01 → split؛ corpus clean → صادقانه not_evaluable)؛ هیچ کاندیدی تأیید/رد نمی‌شود — فقط شمارش | test_cal_runner.py (sweep texture) + smoke step 3 | CandidateResult table | T-12.2.2, T-12.2.3 | SPEC §6 | sweep tests + SMOKE | PASS | TM (T-12.2.4) / 2026-10-08 |
| AC-12.2.3 | WP-12.2 | ایزوله و صفر-اثر: تمام فایل‌های تولیدشده زیر workspace (rglob provenance)؛ corpus store بایت-پایدار قبل/بعد از اجرا (digest row-level)؛ ردِ اجرای مجدد در workspace مصرف‌شده (CalibrationRunRefused — یک اجرا به‌ازای هر workspace با run-manifest)؛ mismatch address / unverified corpus / config خراب (۷ parametrized) → refusals تایپ‌دار پیش از هر کار pipeline | test_cal_boundary.py + smoke steps 6/8 | isolation + refusal evidence | T-12.2.2, T-12.2.3 | SPEC §2.2/§2.8/§8 | provenance + refusal tests | PASS | TM (T-12.2.4) / 2026-10-08 |
| AC-12.2.4 | WP-12.2 | مرزها: بدون هر import test-helper (AST + رشته‌ای)؛ import surface انحصاراً pipeline فروزن + corpus + capture (allowlist AST)؛ sweep «هیچ package تولیدی calibration را import نمی‌کند» + smoke runnerهای قبلی؛ گزارش = تنها خروجی (package هیچ فایلی نمی‌نویسد؛ runner می‌نویسد)؛ بدون ratification/تغییر آستانه (D-07/D-08 دست‌نخورده)؛ vocabulary sweep (بدون Sale/Customer/Inventory/DigitalInvoice)؛ additive-only — Frozen P1–P11.1 byte-untouched (رگرسیون کامل) | test_cal_boundary.py + full regression + git diff | AST/sweep probes + git diff صفر | T-12.2.2, T-12.2.3, T-12.2.4 | SPEC §2/§11 | AST + sweeps + رگرسیون کامل | PASS | TM (T-12.2.4) / 2026-10-08 |

Evidence note (P12.2): 33/33 dedicated tests PASSED ×3 independent repeats؛
SMOKE 19/19 (run_smoke_calibration — 8-step cold-start)؛ رگرسیون کامل 1440
جمع‌کل = 1439 PASSED + ۱ flake ثبت‌شدهٔ از پیش موجود (همان flake تاریخ‌حساس
WP-7.1 — verbatim؛ تفکیک طبق Flake Policy).

Implementation note (P12.2 — کشف مستندشده برای PO/TM): gate output-present
فروزنِ derivation (سرویس فروزن WP-4.2: «derived values never shadow read
fields») یعنی سند دارای gross چاپ‌شده هرگز DERIVED gross نمی‌گیرد و rules
مرجع origin=derived مسیر DEFERRED/REVIEW می‌روند. رفتار فروزن تغییر نکرد؛
قالب clean بدون خط gross طراحی شد (اثبات مسیر derivation/ACCEPTED) و سطح
اندازه‌گیری D-08 در قالب rounding-probe با gross چاپ‌شده ماند. این یافته خودش
یک observation کالیبراسیون معنادار برای PO است: اسناد با gross چاپ‌شده به
REVIEW می‌روند تا زمانی که یک formula/rule تأییدشده برای مقایسهٔ gross
چاپ‌شده در ruleset عملیاتی قرار بگیرد (تصمیم TM/PO — خارج از اختیار Agent).

Boundary declaration (P12): WP-12.3 (Threshold Ratification) DEFERRED —
تصمیم انحصاری PO/G4؛ هیچ مقدار آستانه‌ای ratify/تغییر/ارزیابی نشد (فقط
شمارش). WP-11.2 DEFERRED — Decision Package تحویل شد
(specs/WP-11.2-decision-package.md؛ ۱۷ قلم با classification)؛ هیچ Adapter/نگاشت/فرضی ساخته نشد.

---

## P1 — WP-1.2 (S1 Fingerprint & Integrity — Hardening) — Mission «CONTINUE FORWARD BEYOND BLOCKED P12 DECISIONS» (2026-10-09)

| AC ID | WP | پذیرش (Acceptance Criterion) | Evidence Type | Output Artifact | Tasks | محل تعریف | Tests | نتیجه | تصویب |
|---|---|---|---|---|---|---|---|---|---|
| AC-1.2.1 | WP-1.2 | ماتریس لبهٔ DECLARED کامل (E1..E11 — خالی/تک‌بایت/4MiB/چندزبانه/magic/جهش مرزی/type/فیلدهای hostile/fail-closed سطح ingest/کاوش store-defect/framing) روی لایهٔ فروزن WP-1.1 اجرا و ثبت شده؛ DETERMINISTIC (×2) و CONTENT-SENSITIVE روی همهٔ کلاس‌های مربوطه برقرار؛ هیچ cell حذف نشده | test_s1_hardening.py + خروجی pytest + HARD-RPT-WP12 §2 | Matrix results (per-cell) | T-1.2.1, T-1.2.2 | SPEC-WP12-S1H §4/§5 | ۳۶ تست behavioral | PASS | TM (T-1.2.4) / 2026-10-09 |
| AC-1.2.2 | WP-1.2 | هیچ ورودی لبه‌ای به S1 غیرقطعی یا fail ساکت نمی‌رسد: هر anomaly فقط در outcome تایپ‌دار فروزن (S1ComputationFailure؛ Verdict FAILED/NO_VERDICT؛ IngestSettledFailure/IngestIntegrityFailureHit؛ ReadIntegrityFailure/ReadRefused/ReadVerificationUnavailable؛ CHECK/UNIQUE refusals)؛ هیچ guessed VALID؛ هیچ مسیر ساکت | negative tests نام‌برده (هرکدام outcome تایپ‌دار مشخص) | Typed-outcome evidence | T-1.2.2 | SPEC-WP12-S1H §2.5/§8 | E6/E7/E8/E9/E10 probes | PASS | TM (T-1.2.4) / 2026-10-09 |
| AC-1.2.3 | WP-1.2 | binding تک‌الگوریتم + agility: فقط sha256-v1 (S1_ALGORITHM_ID ثابت فروزن)؛ id ناشناخته/خالی → NO_VERDICT با reason (هرگز guessed)؛ مقایسه فقط درون id برابر (P-S1-6)؛ uniqueness/lookup جفت‌کلید (s1, s1_algorithm_id)؛ مسیر ارتقا فقط مستند (بدون پیاده‌سازی؛ تصمیم TM/PO) | agility tests + HARD-RPT-WP12 §3 | Agility report | T-1.2.2, T-1.2.3 | SPEC-WP12-S1H §6 | cross-id + pair-key tests | PASS | TM (T-1.2.4) / 2026-10-09 |
| AC-1.2.4 | WP-1.2 | مرزها و اثبات: additive-only — فایل‌های موجود byte-identical (git diff در commit؛ صفر تغییر کد تولیدی — OD-SH-F)؛ بدون semantic dedup (D-03/P7)؛ بدون موتور خارجی؛ محدودیت‌های S1 مستند (HARD-RPT-WP12 §4 — ۷ بند)؛ ×≥2 اجرای مستقل سبز + smoke بیستم + رگرسیون کامل | dedicated ×3 + SMOKE ×2 + رگرسیون کامل + git diff | Registers + report + regression | T-1.2.2, T-1.2.3, T-1.2.4 | SPEC-WP12-S1H §2.2/§9 | 36/36 ×3 + SMOKE OK | PASS | TM (T-1.2.4) / 2026-10-09 |

Evidence note (WP-1.2): dedicated hardening suite 36/36 PASSED ×3 independent
repeats؛ SMOKE 20/20 (run_smoke_s1_hardening — ۸ گام cold-start؛ ×2)؛
رگرسیون کامل 1476 جمع‌کل = 1475 PASSED + ۱ flake ثبت‌شدهٔ از پیش موجود
(همان flake تاریخ‌حساس WP-7.1 — verbatim؛ تفکیک طبق Flake Policy). حساب
additive: 1440 + 36 جدید = 1476 — صفر failure جدید.

Implementation note (WP-1.2 — observation ثبت‌شده برای TM/PO): ورودی non-bytes
در مرز ورود ingest (orchestrator) به‌صورت fail-fast با TypeError/AttributeError
از sniff مکانیکی (F-11 که قبل از compute اجرا می‌شود) crash می‌کند — پیش از
هر فراخوانی store، با ZERO residue (اثبات‌شده در suite). ردِ تایپ‌دار
(S1ComputationFailure / NO_VERDICT) در مرز capability است که طراحی فروزن
اعلام کرده. این observation در HARD-RPT-WP12 §2.3 ثبت شد؛ هیچ وصله‌ای در
این WP additive اعمال نشد — هر تغییر در service.py فروزن نیازمند تصمیم
صریح TM/PO است.

Boundary declaration (WP-1.2): هیچ تعریف S1 تغییر نکرد (D-02)؛ هیچ semantic
dedup جدید (D-03/P7)؛ هیچ مقدار retention (DEF4/WP-1.3)؛ هیچ ratification
آستانه (WP-12.3 — PO/G4)؛ additive-only — فایل‌های فروزن P1–P12.2
byte-untouched.
