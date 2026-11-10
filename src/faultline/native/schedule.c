/* Deterministic Pauli schedules. Public Selene error-model descriptor ABI.
 * Ordinals count original physical operations, one-based. Inject AFTER op N.
 * Injection gates and batch timing metadata do not increment the ordinal.
 */
#include <selene/error_model.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <inttypes.h>

#define PI 3.14159265358979323846
#define FAILURE (-1)
typedef struct { uint64_t op, qubit; char pauli; } Fault;
typedef struct {
    Fault *faults;
    size_t count, next;
    uint64_t ordinal, shot, n_qubits;
    FILE *audit;
    SeleneErrno error;
    SimulatorHandle simulator;
    ErrorModelSetResultHandle results;
} State;

static bool number(const char *s, uint64_t *v) {
    if (!s || !*s || *s=='-') return false;
    char *end; errno=0;
    *v=strtoull(s,&end,10);
    return !errno && !*end;
}
static SeleneErrno init(SeleneErrorModelInstance *handle,uint64_t n,uint32_t argc,const char *const *argv) {
    if (argc<1 || (argc-1)%3) return FAILURE;
    State *s=calloc(1,sizeof(*s));
    if (!s) return FAILURE;
    s->n_qubits=n; s->count=(argc-1)/3;
    s->faults=calloc(s->count ? s->count : 1,sizeof(Fault));
    if (!s->faults) {free(s); return FAILURE;}
    for (size_t i=0;i<s->count;i++) {
        Fault *f=&s->faults[i];
        if (!number(argv[1+3*i],&f->op) || !f->op ||
            !number(argv[2+3*i],&f->qubit) || f->qubit>=n ||
            strlen(argv[3+3*i])!=1 || !strchr("XYZ",argv[3+3*i][0]) ||
            (i && f->op<s->faults[i-1].op)) {
            free(s->faults); free(s); return FAILURE;
        }
        f->pauli=argv[3+3*i][0];
    }
    if (*argv[0]) {
        s->audit=fopen(argv[0],"w");
        if (!s->audit) {free(s->faults); free(s); return FAILURE;}
    }
    *handle=s; return 0;
}
static SeleneErrno finish(SeleneErrorModelInstance h) {
    State *s=h;
    int failed=s->audit && fclose(s->audit);
    free(s->faults); free(s);
    return failed ? FAILURE : 0;
}
static SeleneErrno start(SeleneErrorModelInstance h,uint64_t shot,uint64_t seed) {
    (void)seed; State *s=h;
    s->ordinal=0; s->next=0; s->shot=shot; s->error=0;
    if (s->audit) fprintf(s->audit,"{\"event\":\"shot_start\",\"shot\":%"PRIu64"}\n",shot);
    return 0;
}
static SeleneErrno end(SeleneErrorModelInstance h) {
    State *s=h;
    if (s->next!=s->count && !s->error) s->error=FAILURE;
    if (s->audit) {
        fprintf(s->audit,"{\"event\":\"shot_end\",\"shot\":%"PRIu64",\"operations\":%"PRIu64",\"injections\":%zu,\"status\":%d}\n",s->shot,s->ordinal,s->next,s->error);
        if (fflush(s->audit)) s->error=FAILURE;
    }
    return s->error;
}
static void fault_after(State *s) {
    while (!s->error && s->next<s->count && s->faults[s->next].op==s->ordinal) {
        Fault f=s->faults[s->next++];
        SeleneErrno e=0;
        if (f.pauli=='Z') {
            e=s->simulator.interface.rz_fn ? s->simulator.interface.rz_fn(s->simulator.instance,f.qubit,PI) : FAILURE;
        } else {
            e=s->simulator.interface.rxy_fn ? s->simulator.interface.rxy_fn(s->simulator.instance,f.qubit,PI,f.pauli=='Y' ? PI/2 : 0) : FAILURE;
        }
        if (s->audit) fprintf(s->audit,"{\"event\":\"fault\",\"shot\":%"PRIu64",\"after\":%"PRIu64",\"qubit\":%"PRIu64",\"pauli\":\"%c\",\"status\":%d}\n",s->shot,s->ordinal,f.qubit,f.pauli,e);
        if (e) s->error=e;
    }
}
static void record(State *s,const char *kind,uint64_t q,uint64_t r,int result,double theta,double phi) {
    ++s->ordinal;
    if (s->audit) {
        fprintf(s->audit,"{\"event\":\"op\",\"shot\":%"PRIu64",\"ordinal\":%"PRIu64",\"kind\":\"%s\",\"qubits\":[%"PRIu64, s->shot,s->ordinal,kind,q);
        if (!strcmp(kind,"RZZ") || !strcmp(kind,"RPP")) fprintf(s->audit,",%"PRIu64,r);
        fprintf(s->audit,"],\"theta\":%.17g,\"phi\":%.17g,\"result\":%d}\n",theta,phi,result);
        if (ferror(s->audit)) s->error=FAILURE;
    }
    fault_after(s);
}
static void rxy(void *h,uint64_t q,double t,double p) {
    State*s=h; if(s->error)return;
    s->error=s->simulator.interface.rxy_fn ? s->simulator.interface.rxy_fn(s->simulator.instance,q,t,p) : FAILURE;
    if(!s->error) record(s,"RXY",q,0,-1,t,p);
}
static void rz(void *h,uint64_t q,double t) {
    State*s=h; if(s->error)return;
    s->error=s->simulator.interface.rz_fn ? s->simulator.interface.rz_fn(s->simulator.instance,q,t) : FAILURE;
    if(!s->error) record(s,"RZ",q,0,-1,t,0);
}
static void rzz(void *h,uint64_t q,uint64_t r,double t) {
    State*s=h; if(s->error)return;
    s->error=s->simulator.interface.rzz_fn ? s->simulator.interface.rzz_fn(s->simulator.instance,q,r,t) : FAILURE;
    if(!s->error) record(s,"RZZ",q,r,-1,t,0);
}
static void rpp(void *h,uint64_t q,uint64_t r,double t,double p) {
    State*s=h; if(s->error)return;
    s->error=s->simulator.interface.rpp_fn ? s->simulator.interface.rpp_fn(s->simulator.instance,q,r,t,p) : FAILURE;
    if(!s->error) record(s,"RPP",q,r,-1,t,p);
}
static void reset(void *h,uint64_t q) {
    State*s=h; if(s->error)return;
    s->error=s->simulator.interface.reset_fn(s->simulator.instance,q);
    if(!s->error) record(s,"RESET",q,0,-1,0,0);
}
static void measure_common(State*s,uint64_t q,uint64_t result_id,bool leaked) {
    if(s->error)return;
    SeleneErrno value=s->simulator.interface.measure_fn(s->simulator.instance,q);
    if(value<0 || value>1) {s->error=FAILURE;return;}
    if(leaked) s->results.interface.set_u64_result_fn(s->results.instance,result_id,(uint64_t)value);
    else s->results.interface.set_bool_result_fn(s->results.instance,result_id,value!=0);
    record(s,leaked?"MEASURE_LEAKED":"MEASURE",q,0,value,0,0);
}
static void measure(void *h,uint64_t q,uint64_t id) {measure_common(h,q,id,false);}
static void measure_leaked(void *h,uint64_t q,uint64_t id) {measure_common(h,q,id,true);}
static void custom(void *h,size_t tag,const void *data,size_t n) {
    (void)tag;(void)data;(void)n;
    State*s=h; if(!s->error)record(s,"CUSTOM_NOOP",0,0,-1,0,0);
}
static void timing(void *h,uint64_t start,uint64_t duration) {(void)h;(void)start;(void)duration;}
static SeleneErrno operations(SeleneErrorModelInstance h,RuntimeExtractOperationHandle batch,SimulatorHandle sim,ErrorModelSetResultHandle results) {
    State*s=h; s->simulator=sim; s->results=results;
    RuntimeGetOperationHandle callbacks={.instance=s,.interface={
        .measure_fn=measure,.measure_leaked_fn=measure_leaked,.reset_fn=reset,
        .custom_fn=custom,.set_batch_time_fn=timing,.rxy_fn=rxy,.rz_fn=rz,
        .rzz_fn=rzz,.rpp_fn=rpp}};
    batch.interface.extract_fn(batch.instance,callbacks);
    return s->error;
}
static const SeleneErrorModelPluginDescriptorV1 descriptor={
    .struct_size=sizeof(SeleneErrorModelPluginDescriptorV1),
    .api_version=SELENE_ERROR_MODEL_CURRENT_API_VERSION,
    .init_fn=init,.exit_fn=finish,.shot_start_fn=start,.shot_end_fn=end,
    .handle_operations_fn=operations,.get_metrics_fn=NULL
};
const SeleneErrorModelPluginDescriptorV1 *selene_error_model_get_plugin_descriptor_v1(void) {return &descriptor;}
