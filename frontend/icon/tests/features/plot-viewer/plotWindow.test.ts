import { tryOpenPlotWindow } from "../../../src/features/plot-viewer/plotWindow";

describe("plot popup", () => {
  it("clears the opener before navigating and requests a resizable popup", () => {
    const popup = { opener: {}, location: { replace: jest.fn() }, close: jest.fn() };
    popup.location.replace.mockImplementation(() => expect(popup.opener).toBeNull());
    const open = jest.fn(() => popup as unknown as Window);
    expect(
      tryOpenPlotWindow("https://example.test/data/2/plot/readout/0?device=synthetic", {
        open,
      }),
    ).toBe(true);
    expect(open).toHaveBeenCalledWith(
      "",
      "_blank",
      expect.stringContaining("popup=yes"),
    );
    expect(open).toHaveBeenCalledWith(
      "",
      "_blank",
      expect.stringContaining("resizable=yes"),
    );
    expect(popup.location.replace).toHaveBeenCalledWith(
      "https://example.test/data/2/plot/readout/0?device=synthetic",
    );
  });
  it("leaves ordinary link fallback available when blocked", () => {
    expect(tryOpenPlotWindow("/data/2", { open: jest.fn(() => null) })).toBe(false);
    expect(
      tryOpenPlotWindow("/data/2", {
        open: jest.fn(() => {
          throw new Error("blocked");
        }),
      }),
    ).toBe(false);
  });
  it("closes an unusable blank popup before falling back", () => {
    const close = jest.fn();
    const popup = {
      opener: {},
      location: {
        replace: () => {
          throw new Error("navigation failed");
        },
      },
      close,
    };
    expect(
      tryOpenPlotWindow("/data/2", { open: jest.fn(() => popup as unknown as Window) }),
    ).toBe(false);
    expect(close).toHaveBeenCalledTimes(1);
  });
});
