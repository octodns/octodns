$ORIGIN invalid.records.
@           3600 IN	SOA	ns1.invalid.records. root.invalid.records. (
                        2018071501		; Serial
                        3600    ; Refresh (1 hour)
                        600     ; Retry (10 minutes)
                        604800  ; Expire (1 week)
                        3600    ; NXDOMAIN ttl (1 hour)
                    )

; NS Records
@           3600  IN  NS  ns1.invalid.records.
@           3600  IN  NS  ns2.invalid.records.
under       3600  IN  NS  ns1.invalid.records.
under       3600  IN  NS  ns2.invalid.records.

; SRV Records
_srv._tcp   600   IN  SRV 10 20 30 foo-1.invalid.records.
_srv._tcp   600   IN  SRV 10 20 30 foo-2.invalid.records.
_invalid    600   IN  SRV 10 20 30 foo-3.invalid.records.

; TXT Records
txt         600   IN  TXT "Bah bah black sheep"
txt         600   IN  TXT "have you any wool."
txt         600   IN  TXT "v=DKIM1;k=rsa;s=email;h=sha256;p=A/kinda+of/long/string+with+numb3rs"

; MX Records
mx          300   IN  MX  10  smtp-4.invalid.records.
mx          300   IN  MX  20  smtp-2.invalid.records.
mx          300   IN  MX  30  smtp-3.invalid.records.
mx          300   IN  MX  40  smtp-1.invalid.records.

; A Records
@           300   IN  A   1.2.3.4
@           300   IN  A   1.2.3.5
www         300   IN  A   2.2.3.6
wwww.sub    300   IN  A   2.2.3.6

; AAAA Records
aaaa        600   IN  AAAA  2601:644:500:e210:62f8:1dff:feb8:947a

; CNAME Records
cname       300   IN  CNAME   invalid.records.
included    300   IN  CNAME   invalid.records.
