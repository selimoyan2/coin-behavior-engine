# Kesin Zamansal Örtüşme Metodolojisi ve Doğrulama Raporu

**Kanonik Model:** `CBE-0.7.0` (FROZEN)  
**Taahhüt:** `cd588ebfd06903c82ab9eaa7f30e18378adf1bdc`  

## 1. Matematiksel ve Metodolojik Şartlar
Bilimsel karşılaştırmanın geçerli sayılabilmesi için aşağıdaki zamansal şartlar katı olarak zorunlu kılınmıştır:

1. **Doğrulanmış Sınırlar:** Her iki adayın da doğrulanmış ISO-8601 UTC başlangıç (`observation_start_utc`) ve bitiş (`observation_end_utc`) damgalarına sahip olması zorunludur. Sınırları eksik adaylar doğrudan `INSUFFICIENT_OVERLAP_EVIDENCE` kodu ile reddedilir.
2. **Kadans Uyumu:** Her iki aday aynı zaman aralığı kadansına (`window_cadence`) sahip olmalıdır.
3. **Asgari 100 Ortak Gözlem:** Adayların kesişen zaman penceresindeki ortak gözlem sayısı $N_{\text{shared}} \ge 100$ olmalıdır:
   $$N_{\text{shared}} = \left\lfloor \frac{\min(T_{e1}, T_{e2}) - \max(T_{s1}, T_{s2})}{\Delta t} \right\rfloor \ge 100$$
4. **Ayrık Pencerelerin Reddi:** Ortak kesişimi olmayan ayrık pencereler (`DISJOINT_OBSERVATION_WINDOWS`) kesinlikle reddedilir.
5. **Yinelenen Zaman Damgalarının Reddi:** Zaman serisi içerisinde yinelenen gözlem noktaları tespit edildiğinde `DUPLICATE_OBSERVATION_TIMESTAMPS` hatası ile işlem durdurulur.

## 2. Test Edilen Eşleşmeler
- **`RES-REGIME-01` vs `RES-ANALOG-01`:** `FAIL_CLOSED` — `INSUFFICIENT_OVERLAP_EVIDENCE` (Zaman sınırları eksik).
- **`RES-FUND-01` vs `RES-REGIME-01`:** `FAIL_CLOSED` — `SAMPLING_CADENCE_MISMATCH` (8h vs 1h kadans uyuşmazlığı).
- **`RES-COMPAT-01` vs `RES-COMPAT-02`:** `PASS` — 3624 ortak saatlik gözlem ($\ge 100$).
