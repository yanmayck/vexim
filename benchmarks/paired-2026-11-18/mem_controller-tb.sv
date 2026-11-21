module tb;
logic clk=0, rst=1, cmd_valid=0, cmd_write=0, w_valid=0, r_ready=0;
logic mem_ready=0, mem_w_ready=0, mem_r_valid=0;
logic [39:0] cmd_addr=0, mem_addr;
logic [7:0] cmd_beats=0, mem_beats, w_strb=0, mem_w_strb;
logic [63:0] w_data=0, mem_r_data=0, r_data, mem_w_data;
logic cmd_ready, w_ready, r_valid, r_last, mem_valid, mem_write;
logic mem_w_valid, mem_r_ready, done;
mem_controller dut(.*);

logic [39:0] keys[0:1023];
logic [63:0] words[0:1023];
int used=0;

function automatic int locate(input logic [39:0] addr);
  for(int i=0;i<used;i++) if(keys[i]==addr) return i;
  return -1;
endfunction

function automatic logic [63:0] load_word(input logic [39:0] addr);
  int idx;
  idx=locate(addr);
  return idx<0 ? 64'h0942_83bf_56dc_017a : words[idx];
endfunction

task automatic store_word(input logic [39:0] addr, input logic [63:0] data,
                          input logic [7:0] mask);
  int idx;
  idx=locate(addr);
  if(idx<0) begin
    if(used==1024) $fatal(1,"sparse model full");
    idx=used; keys[idx]=addr; words[idx]=64'h0942_83bf_56dc_017a; used++;
  end
  for(int lane=0;lane<8;lane++) if(mask[lane]) words[idx][lane*8+:8]=data[lane*8+:8];
endtask

function automatic logic [63:0] payload(input int seed, beat);
  return (64'h9e3779b97f4a7c15 * (64'(beat)+1)) ^ (64'h0102040810204080 * 64'(seed));
endfunction

function automatic logic [7:0] strobe(input int seed, beat);
  return seed==0 ? 8'hff : 8'(seed*17+beat*13);
endfunction

task automatic edge_cycle;
  clk=1; #1; clk=0; #1;
endtask

task automatic transaction(input bit writing, input logic [39:0] base,
                           input int count, seed);
  int host_off, mem_off, desc_left, cap, expected_count;
  bit accepted, finished, hold_desc, hold_write, hold_read;
  bit take_cmd, take_desc, take_host, take_mem, final_beat;
  logic [39:0] expected_addr;
  host_off=0; mem_off=0; desc_left=0; accepted=0; finished=0;
  hold_desc=0; hold_write=0; hold_read=0;
  cmd_valid=1; cmd_write=writing; cmd_addr=base; cmd_beats=8'(count);
  w_valid=0; r_ready=0; mem_r_valid=0;
  for(int cycle=0;cycle<4000 && !finished;cycle++) begin
    mem_ready=(cycle%5)==4;
    mem_w_ready=(cycle%7)<4;
    r_ready=(cycle%6)>2;
    if(!w_valid && accepted && writing && host_off<count && cycle%5!=2)
      w_valid=1;
    if(w_valid) begin w_data=payload(seed,host_off); w_strb=strobe(seed,host_off); end
    if(!mem_r_valid && !writing && desc_left>0 && cycle%7!=2) begin
      mem_r_valid=1;
      mem_r_data=load_word(base+40'(8*mem_off));
    end
    #1;
    if(accepted && cmd_ready) $fatal(1,"accepted new command while busy");
    expected_addr=base+40'(8*mem_off);
    cap=(4096-int'(expected_addr[11:0]))/8;
    expected_count=count-mem_off;
    if(expected_count>16) expected_count=16;
    if(expected_count>cap) expected_count=cap;
    if(hold_desc && !mem_valid) $fatal(1,"dropped stalled descriptor");
    if(hold_write && !mem_w_valid) $fatal(1,"dropped stalled memory write");
    if(hold_read && !r_valid) $fatal(1,"dropped stalled host read");
    if(mem_valid && (!accepted || desc_left!=0 || mem_addr!==expected_addr ||
                    mem_beats!==8'(expected_count) || mem_write!==writing))
      $fatal(1,"descriptor at %h: got %h/%d expected %h/%d",base,mem_addr,mem_beats,expected_addr,expected_count);
    if(mem_w_valid && (!writing || !accepted || desc_left==0 ||
       mem_w_data!==payload(seed,mem_off) || mem_w_strb!==strobe(seed,mem_off)))
      $fatal(1,"write beat/strobe mismatch at %h beat %d",base,mem_off);
    if(r_valid && (writing || !accepted || host_off>=count ||
       r_data!==load_word(base+40'(8*host_off)) || r_last!==(host_off==count-1)))
      $fatal(1,"read beat/last mismatch at %h beat %d",base,host_off);
    take_cmd=cmd_valid && cmd_ready;
    take_desc=mem_valid && mem_ready;
    take_host=writing ? w_valid && w_ready : r_valid && r_ready;
    take_mem=writing ? mem_w_valid && mem_w_ready : mem_r_valid && mem_r_ready;
    if(take_mem && desc_left==0) $fatal(1,"memory beat outside its descriptor");
    if(!writing && host_off+int'(take_host)>mem_off+int'(take_mem))
      $fatal(1,"ghost read beat");
    if(writing && mem_off+int'(take_mem)>host_off+int'(take_host))
      $fatal(1,"ghost write beat");
    final_beat=(host_off+int'(take_host)==count && mem_off+int'(take_mem)==count);
    if(done!==final_beat) $fatal(1,"done must coincide with the final handshake");
    hold_desc=mem_valid && !mem_ready;
    hold_write=mem_w_valid && !mem_w_ready;
    hold_read=r_valid && !r_ready;
    if(take_mem && writing) store_word(expected_addr,mem_w_data,mem_w_strb);
    edge_cycle();
    if(take_cmd) begin accepted=1; cmd_valid=0; end
    if(take_desc) desc_left=expected_count;
    if(take_host) begin host_off++; w_valid=0; end
    if(take_mem) begin mem_off++; desc_left--; mem_r_valid=0; end
    finished=final_beat;
  end
  if(!finished) $fatal(1,"watchdog: %h %d beats stalled",base,count);
endtask

initial begin
  #1;
  if ({cmd_ready,w_ready,r_valid,mem_valid,mem_w_valid,mem_r_ready,done} !== 7'b0)
    $fatal(1,"handshake during reset");
  edge_cycle(); rst=0;
  transaction(1,40'h0000000ff0,35,0);
  transaction(1,40'h0040000ff0,35,3);
  transaction(1,40'hff40000ff0,35,7);
  transaction(1,40'h0040000ff0,35,9);
  transaction(0,40'h0000000ff0,35,0);
  transaction(0,40'h0040000ff0,35,0);
  transaction(0,40'hff40000ff0,35,0);
  transaction(1,40'hfffffffe00,64,5);
  transaction(0,40'hfffffffe00,64,0);
  transaction(1,40'h8100100ff8,255,2);
  transaction(0,40'h8100100ff8,255,0);
  cmd_valid=1; cmd_write=1; cmd_addr=40'h18; cmd_beats=8'd4; mem_ready=0;
  #1; if(!cmd_ready) $fatal(1,"not idle before reset scenario");
  edge_cycle(); cmd_valid=0;
  #1; if(!mem_valid) $fatal(1,"descriptor missing before reset");
  rst=1; #1;
  if ({cmd_ready,w_ready,r_valid,mem_valid,mem_w_valid,mem_r_ready,done} !== 7'b0)
    $fatal(1,"outstanding work was not suppressed during reset");
  edge_cycle(); rst=0;
  transaction(0,40'hff40000ff0,1,0);
  $display("PASS");
  $finish;
end
endmodule
