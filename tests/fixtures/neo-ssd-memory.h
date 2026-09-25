static const unsigned char data_0[] = {0,0,0,0,0,1,0,0};
static const unsigned char data_1[] = {0,0,0,0,2,0,0,0};
static const unsigned char data_2[] = {1,0,0,0};
static const unsigned char data_3[] = {0,128,165,241,1,1,0,0};
static const unsigned char data_4[] = {0,0,32,14,0,0,0,0};
static const unsigned char data_5[] = {0,64,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,64,0,0,0,1,0,0,0,192,34,0,1,0,0,0,0,128,132,255,1,1,0,0,0,192,34,0,0,0,0,0,0,128,132,255,1,1,0,0,0,0,65,0,0,0,0,0};
static const char *paths[] = {"/chosen","/arm-io/ans/iop-ans-nub"};
static const struct { int node; const char *name; const void *data; u32 size; } props[] = {{0,"dram-base",data_0,8},{0,"dram-size",data_1,8},{1,"pre-loaded",data_2,4},{1,"region-base",data_3,8},{1,"region-size",data_4,8},{1,"segment-ranges",data_5,64}};
