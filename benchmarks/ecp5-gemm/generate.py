"""Generate comparable Vexim and readable SystemVerilog for a signed INT8 array."""
from pathlib import Path

N = 12
TOP = "gemm"
PORTS = (
    [("input", "clk", 1), ("input", "rst", 1), ("input", "step", 1),
     ("input", "row", 4), ("input", "col", 4)]
    + [("input", f"west_{i}", 8) for i in range(N)]
    + [("input", f"north_{i}", 8) for i in range(N)]
    + [("output", "result", 32)]
)


def vexim():
    lines = [f"module {TOP}"]
    lines.extend(f"{mode} {name} u{width}" for mode, name, width in PORTS)

    def wire(name, width, expr=None):
        lines.append(f"wire {name} u{width}")
        if expr is not None:
            lines.append(f"comb {name} {expr}")

    def register(name, width, data):
        wire(name, width)
        wire(f"{name}_next", width, f"mux step {data} {name}")
        lines.append(f"sync {name} clk rst {name}_next")

    wire("zero32", 32, "const 0")
    wire("neg8", 8, "const 255")
    wire("zero8", 8, "const 0")
    wire("neg16", 16, "const 65535")
    wire("zero16", 16, "const 0")
    for index in range(N):
        wire(f"index{index}", 4, f"const {index}")
        wire(f"row{index}", 1, f"eq row index{index}")
        wire(f"col{index}", 1, f"eq col index{index}")
    selections = []
    for r in range(N):
        for c in range(N):
            tag = f"p{r}_{c}"
            east_in = f"west_{r}" if c == 0 else f"p{r}_{c-1}_east"
            south_in = f"north_{c}" if r == 0 else f"p{r-1}_{c}_south"
            register(f"{tag}_east", 8, east_in)
            register(f"{tag}_south", 8, south_in)
            for key, src in (("a", east_in), ("b", south_in)):
                base = f"{tag}_{key}"
                wire(f"{base}_sign", 1, f"slice {src} 7 7")
                wire(f"{base}_hi", 8, f"mux {base}_sign neg8 zero8")
                wire(f"{base}_wide", 16, f"concat {base}_hi {src}")
            wire(f"{tag}_mul", 16, f"mul {tag}_a_wide {tag}_b_wide")
            register(f"{tag}_product", 16, f"{tag}_mul")
            wire(f"{tag}_sign", 1, f"slice {tag}_product 15 15")
            wire(f"{tag}_hi", 16, f"mux {tag}_sign neg16 zero16")
            wire(f"{tag}_term", 32, f"concat {tag}_hi {tag}_product")
            wire(f"{tag}_sum", 32, f"add {tag}_acc {tag}_term")
            register(f"{tag}_acc", 32, f"{tag}_sum")
            wire(f"{tag}_select", 1, f"and row{r} col{c}")
            wire(f"{tag}_selected", 32, f"mux {tag}_select {tag}_acc zero32")
            selections.append(f"{tag}_selected")
    level = 0
    while len(selections) > 1:
        combined = []
        for i in range(0, len(selections) - 1, 2):
            target = f"select{level}_{i//2}"
            wire(target, 32, f"or {selections[i]} {selections[i+1]}")
            combined.append(target)
        selections = combined + (selections[-1:] if len(selections) % 2 else [])
        level += 1
    return "\n".join(lines + [f"comb result copy {selections[0]}", "end", ""])


def systemverilog():
    ports = ",\n".join(f"  {mode} logic " + (f"[{width-1}:0] " if width > 1 else "") + name
                       for mode, name, width in PORTS)
    west = ", ".join(f"west_{i}" for i in reversed(range(N)))
    north = ", ".join(f"north_{i}" for i in reversed(range(N)))
    return f"""module {TOP}(
{ports}
);
  localparam N={N};
  wire [8*N-1:0] west={{{west}}};
  wire [8*N-1:0] north={{{north}}};
  logic [7:0] east [0:N-1][0:N-1];
  logic [7:0] south [0:N-1][0:N-1];
  logic signed [15:0] product [0:N-1][0:N-1];
  logic signed [31:0] accum [0:N-1][0:N-1];
  wire [31:0] result_row [0:N-1];
  for(genvar r=0;r<N;r++) begin: rows
    wire [31:0] selected [0:N];
    assign selected[0]=0;
    assign result_row[r]=selected[N];
    for(genvar c=0;c<N;c++) begin: cols
      wire signed [7:0] a, b;
      if(c==0) assign a=west[r*8+:8];
      else assign a=east[r][c-1];
      if(r==0) assign b=north[c*8+:8];
      else assign b=south[r-1][c];
      always_ff @(posedge clk) begin
        if(rst) begin
          east[r][c]<=0; south[r][c]<=0;
          product[r][c]<=0; accum[r][c]<=0;
        end else if(step) begin
          east[r][c]<=a; south[r][c]<=b;
          product[r][c]<=a*b;
          accum[r][c]<=accum[r][c]+product[r][c];
        end
      end
      assign selected[c+1]=selected[c] | ((row==r && col==c) ? accum[r][c] : 32'd0);
    end
  end
  always_comb begin
    result=0;
    for(integer r=0;r<N;r++) result=result | result_row[r];
  end
endmodule
"""


def bench():
    connections = ",\n".join(f"    .{side}_{i}({side}[{i}])"
                              for side in ("west", "north") for i in range(N))
    return f"""module tb;
  localparam N={N}, K=24;
  reg clk=0, rst=1, step=0;
  reg [3:0] row=0, col=0;
  reg [7:0] west[0:N-1], north[0:N-1];
  wire signed [31:0] result;
  gemm dut(.clk(clk),.rst(rst),.step(step),.row(row),.col(col),.result(result),
{connections}
  );
  task automatic tick;
    #2; clk=1; #2; clk=0;
  endtask
  function automatic integer a(input integer r,k,frame);
    return ((r*83+k*29+frame*53)%256)-128;
  endfunction
  function automatic integer b(input integer k,c,frame);
    return ((k*67+c*19+frame*41)%256)-128;
  endfunction
  initial begin
    for(integer frame=0;frame<3;frame++) begin
      rst=1; step=0; tick(); rst=0;
      for(integer t=0;t<K+2*N;t++) begin
        for(integer i=0;i<N;i++) begin
          west[i]=(t>=i && t-i<K) ? 8'(a(i,t-i,frame)) : 8'd0;
          north[i]=(t>=i && t-i<K) ? 8'(b(t-i,i,frame)) : 8'd0;
        end
        if(t%4==1) begin step=0; tick(); end
        step=1; tick();
      end
      step=0;
      for(integer r=0;r<N;r++) begin
        for(integer c=0;c<N;c++) begin
          integer expected;
          row=4'(r); col=4'(c); expected=0;
          for(integer k=0;k<K;k++) expected+=a(r,k,frame)*b(k,c,frame);
          #2;
          if(result !== expected)
            $fatal(1,"frame %0d r %0d c %0d: got %0d expected %0d",frame,r,c,result,expected);
        end
      end
      row=15; #2; if(result !== 0) $fatal(1,"invalid output index");
    end
    $display("PASS"); $finish;
  end
endmodule
"""


def generate(output):
    output.mkdir(parents=True, exist_ok=True)
    for name, content in (("gemm.vxm", vexim()), ("direct.sv", systemverilog()), ("tb.sv", bench())):
        (output / name).write_text(content)


if __name__ == "__main__":
    import sys
    generate(Path(sys.argv[1]))
