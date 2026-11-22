# Local source dispositions

Complete current-hash TypeScript AST parse; erased-only modules closed structurally. Runtime semantic review remains partial at explicitly listed declarations/import edges. source_range is source extent, not a semantic review claim.

## packages/core/types/agent.ts

Status: partial. SHA-256: a1c494eb9f71de1f08350415eb1b41777387e601da6ace53ba4d639d193c640b. Source: 1-1482.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 114-145, 150-153; trace value imports (none). Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/core/types/api.ts

Status: closed. SHA-256: b9b6d05e8e96becd36ea10ddb30b19cc7581e9803061341722134582c0183f96. Source: 1-750.

Complete current-hash AST contains exclusively erased interfaces/type aliases and type-only imports. No runtime declarations, initializers, callbacks or value imports exist.

Remaining: None.

## packages/core/types/attachment-url.ts

Status: partial. SHA-256: c83769130ad8d227561077c5d10c8183f5f541aadbefed65dcc35023d0d2109f. Source: 1-190.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 7-7, 8-8, 9-10, 14-16, 25-25, 40-42, 56-84, 89-89, 90-93, 94-97, 101-111, 126-141, 143-145, 147-152, 169-189; trace value imports (none). Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/core/types/attachment.ts

Status: closed. SHA-256: bfc65ad645829505721dab3ad5924e47ec80181ab7f6ad035b31d40fe83a9d03. Source: 1-64.

Complete current-hash AST contains exclusively erased interfaces/type aliases and type-only imports. No runtime declarations, initializers, callbacks or value imports exist.

Remaining: None.

## packages/core/types/chat.ts

Status: closed. SHA-256: 1e960c9a3924255923e641980f34e77d54c8104021fa8aecb5b5baadbcf57c8f. Source: 1-371.

Complete current-hash AST contains exclusively erased interfaces/type aliases and type-only imports. No runtime declarations, initializers, callbacks or value imports exist.

Remaining: None.

## packages/core/types/events.ts

Status: closed. SHA-256: d01c4b2593bde2ddd22b23b4c50f357456e7d5424a525817b4c9bb57b3e0442d. Source: 1-757.

Complete current-hash AST contains exclusively erased interfaces/type aliases and type-only imports. No runtime declarations, initializers, callbacks or value imports exist.

Remaining: None.

## packages/core/api/schemas.ts

Status: partial. SHA-256: f75704eeb37705c0f72b4bd89ff89e848289f3fe7cee154b9bed7ff280be674d. Source: 1-4768.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 117-126, 128-134, 136-148, 150-154, 156-173, 175-191, 193-195, 197-199, 206-214, 216-228, 230-232, 238-241, 250-256, 258-260, 262-282, 284-294, 296-305, 312-319, 321-327, 329-331, 333-335, 337-343, 346-351, 353-358, 360-369, 371-376, 378-383, 385-389, 391-393, 395-404, 406-411, 413-417, 419-454, 458-464, 466-469, 471-474, 478-492, 494-494, 496-498, 506-533, 535-540, 542-548, 550-561, 563-568, 570-575, 579-589, 591-593, 595-597, 602-612, 614-624, 626-629, 631-634, 641-655, 657-670, 672-676, 680-684, 689-694, 696-698, 700-706, 708-719, 721-724, 726-729, 731-742, 744-756, 758-761, 763-766, 768-770, 772-772, 774-792, 796-807, 809-812, 814-816, 823-838, 842-842, 844-852, 856-861, 868-885, 902-922, 924-937, 942-963, 965-982, 984-986, 988-990, 992-994, 996-999, 1001-1004, 1011-1026, 1028-1031, 1033-1035, 1111-1118, 1123-1126, 1128-1131, 1133-1137, 1139-1157, 1159-1159, 1160-1160, 1162-1170, 1184-1200, 1204-1218, 1220-1236, 1247-1253, 1255-1259, 1261-1288, 1293-1293, 1295-1295, 1297-1300, 1302-1306, 1308-1314, 1336-1341, 1346-1350, 1352-1374, 1376-1399, 1427-1430, 1432-1450, 1453-1458, 1460-1460, 1464-1467, 1469-1472, 1474-1477, 1479-1482, 1484-1506, 1508-1508, 1513-1528, 1530-1536, 1541-1546, 1548-1563, 1565-1569, 1571-1574, 1579-1579, 1581-1590, 1595-1597, 1599-1603, 1605-1615, 1617-1628, 1630-1637, 1639-1647, 1649-1684, 1686-1688, 1690-1752, 1754-1757, 1773-1777, 1779-1782, 1784-1789, 1791-1793, 1795-1797, 1799-1827, 1829-1831, 1833-1838, 1840-1843, 1845-1845, 1847-1853, 1855-1860, 1865-1875, 1877-1885, 1889-1891, 1893-1896, 1898-1900, 1902-1904, 1909-1911, 1913-1915, 1917-1922, 1924-1930, 1932-1938, 1940-1951, 1953-1959, 1961-1963, 1965-1967, 1969-1974, 1976-1982, 1984-2011, 2013-2018, 2020-2025, 2027-2032, 2034-2037, 2039-2047, 2049-2057, 2059-2062, 2064-2068, 2070-2074, 2076-2080, 2082-2091, 2093-2093, 2095-2097, 2099-2102, 2104-2116, 2118-2132, 2134-2134, 2136-2136, 2138-2152, 2175-2181, 2183-2193, 2195-2195, 2197-2207, 2209-2209, 2214-2221, 2223-2223, 2225-2231, 2233-2233, 2243-2247, 2249-2249, 2251-2255, 2257-2259, 2266-2276, 2278-2278, 2280-2283, 2285-2285, 2287-2297, 2299-2299, 2301-2310, 2312-2312, 2317-2319, 2321-2329, 2331-2354, 2356-2358, 2367-2372, 2374-2377, 2379-2389, 2391-2395, 2397-2403, 2409-2418, 2420-2466, 2472-2481, 2483-2483, 2485-2488, 2499-2512, 2514-2514, 2519-2529, 2531-2551, 2553-2556, 2561-2569, 2571-2574, 2576-2588, 2590-2594, 2596-2612, 2614-2624, 2625-2628, 2629-2629, 2637-2644, 2646-2648, 2650-2657, 2659-2664, 2669-2676, 2678-2678, 2682-2709, 2711-2716, 2717-2717, 2719-2729, 2734-2738, 2740-2744, 2746-2747, 2749-2751, 2753-2766, 2768-2772, 2774-2778, 2786-2811, 2818-2830, 2832-2834, 2836-2838, 2840-2842, 2850-2852, 2857-2861, 2863-2880, 2882-2882, 2883-2883, 2884-2899, 2905-2910, 2912-2918, 2920-2922, 2924-2924, 2946-2954, 2958-2965, 2984-2997, 2999-3031, 3033-3036, 3038-3038, 3040-3043, 3051-3076, 3078-3081, 3083-3086, 3094-3109, 3111-3122, 3124-3138, 3144-3146, 3148-3150, 3152-3176, 3187-3206, 3208-3220, 3228-3235, 3237-3237, 3243-3259, 3261-3264, 3270-3274, 3277-3279, 3285-3291, 3296-3302, 3314-3340, 3344-3354, 3356-3362, 3364-3364, 3368-3382, 3384-3384, 3385-3385, 3396-3401, 3403-3408, 3414-3426, 3428-3433, 3435-3440, 3442-3455, 3457-3462, 3464-3469, 3471-3486, 3488-3493, 3495-3500, 3502-3510, 3512-3512, 3514-3514, 3516-3520, 3522-3526, 3528-3536, 3538-3546, 3548-3550, 3552-3554, 3570-3570, 3575-3578, 3580-3595, 3597-3629, 3631-3703, 3705-3712, 3716-3733, 3736-3749, 3752-3752, 3754-3779, 3781-3792, 3794-3807, 3809-3822, 3824-3847, 3849-3872, 3874-3883, 3901-3905, 3907-3910, 3912-3916, 3921-3930, 3936-3940, 3942-3956, 3964-3972, 3974-3985, 3987-3997, 3999-4003, 4005-4008, 4010-4017, 4019-4023, 4025-4031, 4033-4036, 4038-4042, 4044-4048, 4057-4065, 4067-4074, 4076-4084, 4086-4089, 4091-4095, 4099-4103, 4105-4112, 4116-4120, 4122-4126, 4128-4132, 4134-4145, 4147-4158, 4160-4164, 4166-4169, 4171-4175, 4177-4181, 4186-4193, 4198-4212, 4214-4224, 4226-4229, 4231-4235, 4237-4237, 4239-4246, 4248-4257, 4259-4261, 4263-4263, 4265-4272, 4274-4286, 4288-4288, 4290-4295, 4307-4312, 4314-4317, 4332-4343, 4345-4345, 4347-4354, 4358-4371, 4373-4384, 4386-4386, 4388-4393, 4395-4399, 4401-4410, 4412-4416, 4418-4435, 4437-4445, 4447-4452, 4454-4457, 4459-4479, 4481-4491, 4493-4496, 4498-4503, 4505-4527, 4530-4551, 4552-4552, 4556-4570, 4572-4576, 4578-4581, 4588-4588, 4589-4589, 4590-4590, 4591-4591, 4592-4592, 4593-4593, 4595-4603, 4605-4610, 4612-4619, 4621-4629, 4631-4634, 4636-4639, 4641-4648, 4650-4663, 4665-4670, 4672-4674, 4676-4700, 4702-4705, 4707-4716, 4718-4733, 4735-4735, 4737-4744, 4746-4746, 4748-4753, 4757-4763, 4765-4767; trace value imports zod, ../issues/config/status. Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/core/appearance/theme-css.ts

Status: partial. SHA-256: 36870ae0835512e55427282ffb11e10f8b1220d5eea435bc32406b42821fd7e2. Source: 1-239.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 18-18, 27-28, 31-33, 36-41, 43-43, 44-44, 45-45, 47-47, 48-48, 49-49, 50-51, 52-53, 55-238; trace value imports (none). Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/core/dashboard/failure-class.ts

Status: partial. SHA-256: 980726b90448455e3d56db10c4e9258aba2b9a5b5badbb9f2f756c75e872cc42. Source: 1-113.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 14-22, 34-96, 110-112; trace value imports (none). Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/core/feature-flags/static-provider.ts

Status: partial. SHA-256: 63c11ba1db1861da61ffccf1d2e30b2018b6d19a936b6533b75671f09bbb6cc1. Source: 1-118.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 15-46, 48-75, 77-98, 100-102, 109-113, 115-117; trace value imports ./hash. Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/core/paths/paths.ts

Status: partial. SHA-256: a63f8f935dc9a522a6cc70c500547004e7f2cf7d9a990e4237760f0ad295853c. Source: 1-119.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 15-15, 23-23, 31-31, 34-36, 38-93, 95-106, 114-114, 116-118; trace value imports (none). Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/core/paths/reserved-slugs.ts

Status: partial. SHA-256: 6606c537131bb1628693fb1fd566de5a15e9879e325d5f89d0331bdaf07c41d2. Source: 1-383.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 17-378, 380-382; trace value imports (none). Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/core/shortcuts/platform.ts

Status: partial. SHA-256: 998915efab5db407e0b2b8c21474af708cf21ec8ba49777ef2ee2e60d8fd7e2f. Source: 1-76.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 6-6, 7-7, 9-15, 18-33, 35-39, 41-43, 54-65, 67-71, 73-75; trace value imports (none). Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/core/issues/canonical-id.ts

Status: partial. SHA-256: de6fcf914076ea66733ded5e4acb6046714dcf4489658dde57bbdb548e98c082. Source: 1-124.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 7-7, 10-12, 62-123; trace value imports react, @tanstack/react-query, ./queries, ./read-state. Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/core/issues/status-category.ts

Status: partial. SHA-256: 2bb7ccdfc42e10c75e81b14421110ebd360dc46a76f563b0cb5c5e69c9caa94b. Source: 1-199.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 21-29, 39-42, 46-50, 70-79, 106-127, 130-145, 148-169, 184-189, 192-198; trace value imports ../issue-statuses, ./config. Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/core/issues/timeline-sort.ts

Status: partial. SHA-256: c1a9ddae839cf26b0ca1103c2673b386cdbd7da4f3e9ba0c1a31a2e35c168e15. Source: 1-23.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 14-22; trace value imports (none). Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/core/issues/surface/filter-dependency.ts

Status: partial. SHA-256: 2a7f47faf6f23a13b2898d0291c04891faf1a0051ec80911b4592aa76c2d78a5. Source: 1-103.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 28-33, 55-73, 77-91, 94-102; trace value imports (none). Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/views/issues/utils/status-label.ts

Status: partial. SHA-256: 15b642495cedbc22414e2a1d99ab2c350871c8bb6d919be46f22f00874bb1f54. Source: 1-44.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 1-1, 25-43; trace value imports react, @workpal/core/issue-statuses, @workpal/core/issue-statuses/hooks, ../../i18n. Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/views/issues/utils/status-options.ts

Status: partial. SHA-256: 3e4f80d2f9245b5e47a02856d8cf8b0c6da7a46267d997c72cddccf0034c0097. Source: 1-148.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 1-1, 44-44, 46-86, 88-88, 109-147; trace value imports react, @workpal/core/issues/config, @workpal/core/issue-statuses/hooks, @workpal/core/issue-workflows, @workpal/core/issue-statuses/queries, ./status-label. Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/views/editor/utils/hash-string.ts

Status: partial. SHA-256: f447f8cee921b2341f85468bbfb7a555eb3053e858d684f1efbf879b69496c98. Source: 1-17.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 10-16; trace value imports (none). Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/views/dashboard/utils.ts

Status: partial. SHA-256: 0291f572d74f9a3c8bfd995563b4be97d8ff2a3ba63dcdaef3ccf70fadfcbf22. Source: 1-814.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 57-64, 69-106, 114-142, 158-170, 182-198, 223-277, 282-282, 293-293, 321-351, 356-358, 380-405, 407-413, 415-429, 431-464, 469-476, 483-497, 503-522, 538-542, 546-555, 560-579, 584-603, 614-624, 634-648, 658-673, 681-681, 704-734, 743-749, 758-758, 760-762, 767-778, 803-813; trace value imports @workpal/core/dashboard, ../runtimes/utils. Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/views/skills/lib/origin.ts

Status: partial. SHA-256: b3b15ed8fcf8e6377b1b09b4560c97e5e60c9a7d8164577452eb10f134ceeab1. Source: 1-100.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 23-32, 40-46, 52-56, 73-89, 96-99; trace value imports (none). Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## packages/views/test/shard-timings.json

Status: closed. SHA-256: d14fd7753e0a3f7a4399ee6cf96e685953132ad60120d763f5a8278804466158. Source: 1-579.

JSON parsed as data, with no executable module imports, callbacks or resource loading. Test path keys and timing literals describe shard scheduling input; they do not execute the named tests or establish measured backend behavior.

Remaining: None.

## apps/web/features/landing/i18n/en.ts

Status: partial. SHA-256: 7f71d604e64a95269e3e2f2bd039f915094d5d059c95e80080796a6c93166e34. Source: 1-4435.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 5-4434; trace value imports ../components/shared, ./site-en. Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## apps/web/features/landing/i18n/ja.ts

Status: partial. SHA-256: c885213478e49eedf6e73e50576c91c6c7bfd4ac56df38bb57d85ebfa694ed7a. Source: 1-3923.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 6-3922; trace value imports ../components/shared, ./en, ./site-ja. Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## apps/web/features/landing/i18n/ko.ts

Status: partial. SHA-256: dd3d6f0feefd81e418fd33239cd0b8336b81f4baea549c87c26246c0269c90ae. Source: 1-3944.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 6-3943; trace value imports ../components/shared, ./en, ./site-ko. Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## apps/web/features/landing/i18n/zh.ts

Status: partial. SHA-256: c4acdb47a99243fba22b0f1dd65c7a7ea0c8ed7019447dd3d37faaa3bc8ec150. Source: 1-4415.

Complete current-hash AST parsed; runtime declarations require semantic closure. Source statement anchors below describe source extent, not reviewed bodies.

Remaining: Review runtime declarations at 5-4414; trace value imports ../components/shared, ./site-zh. Call-site and callback ranges are recorded in ast_proof; their effects are not yet semantically closed.

## Parent semantic review follow-up

Ten additional small runtime modules were reviewed completely (source or complete emitted runtime, with type-only syntax erased). Current partition: 15 closed, 12 partial. This supersedes earlier counts; global coverage remains false.

- `packages/core/paths/paths.ts`: Complete emitted runtime reviewed: URI encoding, string construction and prefix/search-param predicates only. Returned navigation paths are not requests in this module.
- `packages/core/paths/reserved-slugs.ts`: Complete AST and emitted runtime reviewed: literal string Set and Set.has only; no imports or transport.
- `packages/core/types/attachment-url.ts`: Complete emitted runtime reviewed: URL parsing, regular expressions, string extraction and attachment-reference predicates only. Download paths are returned values; this module does not retrieve them.
- `packages/core/appearance/theme-css.ts`: Complete AST and emitted runtime reviewed: local CSS scanner and asset-map lookup returning CSS/errors. It neither installs CSS nor retrieves assets; accepted data URLs and fragment references are values, not network calls here.
- `packages/core/dashboard/failure-class.ts`: Full source reviewed: constant classification arrays/maps and lookup with other fallback; no imports or I/O.
- `packages/core/feature-flags/static-provider.ts`: Full source and imported hash.ts reviewed: in-memory rule storage, allow/deny matching and deterministic TextEncoder/FNV-1a percentage bucketing. No network; context inputs are ordinary values.
- `packages/core/shortcuts/platform.ts`: Full source reviewed: navigator fields, Electron/desktopAPI presence and configured local state determine platform. No native bridge invocation or transport.
- `packages/core/issues/timeline-sort.ts`: Full source reviewed: type-only import and in-place array sorting by created_at/id; no I/O.
- `packages/views/editor/utils/hash-string.ts`: Full source reviewed: local DJB2 string loop and base-36 result; no dependencies or I/O.
- `packages/views/skills/lib/origin.ts`: Full source reviewed: type-only imports, origin discriminants, URL parsing and host/protocol validation, and local file counts. External source URLs are returned values; no fetch or navigation occurs here.

## Reconciled follow-up reviews

Current partition: 27 closed, 0 partial. Subsequent translation, schema, dashboard and status/retry proofs are linked per source in JSON; these supersede earlier remaining-edge notes. Global coverage remains false.
